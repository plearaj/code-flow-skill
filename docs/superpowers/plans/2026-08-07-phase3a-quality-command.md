# Code Flow 1.2.0 — Phase 3a Quality Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `code-flow.quality` — a second installed command that reads the map `code-flow.map` already produced and writes `quality-report.json` and `quality-report.md`, reporting DRY, KISS and YAGNI findings with `file:line` evidence and honest coverage.

**Architecture:** This repository is an *installer*, not an analyzer. Both CLIs copy prompt-template files into a consuming project; all analysis behavior lives in the prompt text of the templates. Phase 3a therefore has two halves that barely touch: **installer plumbing** (Task 1 — real code, in two languages, so a second command per host gets copied) and **prompt text** (Tasks 2-5 — the detectors, the gating rules, the outputs). Unlike phase 2, the installers *do* change here, because there are now files to install.

**Tech Stack:** Node 24 (`node:test`, built in), Python 3.12 + pytest, hatchling, uv. No new dependencies of any kind.

## Global Constraints

- Target version is exactly `1.2.0`, set identically in `package.json` and `pyproject.toml`. Phase 3a is additive within 1.x — it carries no breaking change.
- Root `templates/` is the single source of truth. `src/code_flow_skill/templates/` must not exist.
- Installers stay **plain file copies**. No read-modify-write, no guard strings, no idempotency logic — copying is idempotent by construction. `--tool` semantics are unchanged; each host simply gains one more file.
- The two installers' file lists must stay in step. `test/install.test.js` and `tests/test_installer_python.py` assert the same literal `EXPECTED_ALL` list, and that is what holds them there. Change one, change the other, in the same commit.
- Every path written into a generated artifact uses forward slashes and is repo-relative. `meta.root` is the one absolute path.
- Reports say **"catalogued"**, never "all". Discovery was Glob/Grep/Read, not an AST walk, so the map is best-effort and the report must never claim completeness.
- `code-flow.quality` **never writes to source code.** It writes only `Code_Flows/quality-report.json` and `Code_Flows/quality-report.md`. If a task seems to require editing source, stop and report — it means the design was misread.
- Severity is **rule-based**, from the thresholds in Task 3. Never impressionistic. A detector that cannot apply its threshold does not emit a finding.
- Windows is the development platform. `npm test` is `node --test "test/**/*.test.js"` — the bare `node --test test/` form fails with MODULE_NOT_FOUND on this machine's Node v24.11.1. Python tests: `uv run --group dev pytest -v`.
- No runtime dependencies in either package. `pytest` stays a dev dependency; Node uses its built-in runner.
- Do not use `git add -A`; stage explicit paths.

### Host parity rule (binding on every task)

Three host templates must stay semantically equivalent:

| Host | File | Shape |
|---|---|---|
| Claude | `templates/claude/code-flow.quality.md` | Markdown, `#### N. Title` sections, `$ARGUMENTS` |
| Gemini | `templates/gemini/code-flow.quality.toml` | The same prose inside a TOML `prompt = '''…'''` string |
| Copilot | `templates/copilot/code-flow.quality.prompt.md` | Markdown with `mode: agent` frontmatter, a numbered list plus trailing sections |

**The map templates carry a 27-line Claude/Gemini divergence. The quality templates start with none, and must keep none.** That divergence is inherited history — three deliberate classes (Claude-only tool names, four-backtick fences around examples containing nested fences, and `∈`/`≤` versus ASCII) plus two wording variants. None of those classes has to arise in a new file, so:

- **Claude and Gemini must be byte-identical from `#### 1.` onward. Baseline 0.** The parity script in Task 1 Step 8 checks it, and every later task re-runs it.
- Achieve that by construction, not by reconciliation afterwards:
  - **Name no host-specific tool.** Write "Read `Code_Flows/index.json`" and "search the inventory", never "Use the `Read` tool" or "Use `Grep`". Every instruction in this command is reading files the map already wrote — there is no step that needs a named tool.
  - **Use three-backtick fences only.** Claude's map template needs four-backtick fences because its examples contain nested fences. No example in this command does: they are JSON objects and a flat markdown excerpt. Keep it that way. If an example you are adding would contain a fence, restructure the example rather than widening the fence.
  - **Write ASCII.** "is one of", "at least", "up to" — never `∈`, `≥`, `≤`.
- **Copilot says the same thing in its own voice** — its numbered-list register, not Claude's heading register. Same rules, same field names, same thresholds, same phrasings.
- **Phase 1 lost four review rounds to host drift, and phase 2 lost none.** The difference was writing each rule once as canonical text and applying it to three hosts, rather than drafting per-host blocks. This plan gives each new rule **once**. Apply that one block to all three hosts. Do not ask for a separate per-host block; that is how phase 1's Copilot template got abridged five times.
- At the end of each task, read all three templates **end-to-end** and **derive** — do not assert — that each rule the task added is present in each host. Record the derivation in the task report. Every phase-1 miss was a rule present in two hosts and absent from the third, and every one was *outside* the section under review.

### What the map already guarantees

These are facts about the artifacts, established in phases 1 and 2. The quality command reads them and must not re-derive them:

- `Code_Flows/index.json` carries `meta` (`root`, `generated`, `mode`, `detail`, `schema: 1`), `coverage` (`filesScanned`, `filesSkipped`, `skipReason`, `functionsCatalogued`, `entryPointsFound`, `flowsTraced`), `files[]` (`path`, `size`, `hash`), and `flows[]` (`slug`, `title`, `file`, `entry`, `nodes`).
- `Code_Flows/inventory.json` carries `schema: 1` and `functions[]` (`id`, `name`, `file`, `line`, `loc`, `signature`, `purpose`, `role`, `exported`, and `snippet` when `--detail` allowed one).
- Each `Code_Flows/<slug>.json` carries `meta`, `nodes[]` and `edges[]`. Node `id` is derived from `file` + `name` by the same rule the inventory uses — **that join is the whole point**, and it is what makes `inventory − reachable` computable.
- `meta.mode` is `whole-code-base` or `feature`. `meta.detail` is `thin`, `standard` or `verbose`.
- `coverage.flowsTraced` below `coverage.entryPointsFound` means the trace pass is incomplete. That is not an error.

## File Structure

**Created:**
- `docs/superpowers/plans/2026-08-07-phase3a-quality-command.md` — this plan
- `templates/claude/code-flow.quality.md`
- `templates/gemini/code-flow.quality.toml`
- `templates/copilot/code-flow.quality.prompt.md`
- `examples/sample-report.json` — the finding-schema fixture
- `tests/test_report_schema.py` — executable check that the fixture obeys the finding schema

**Modified:**
- `bin/install.js` — one file per tool becomes a list of files per tool
- `src/code_flow_skill/cli.py` — the same restructure; three per-host functions collapse into one
- `test/install.test.js` — `EXPECTED_ALL` gains three entries; new per-host assertions
- `tests/test_installer_python.py` — the same, plus the byte-identity map
- `tests/test_packaging.py` — wheel contents gain three files; version assertion moves to `1.2.0`
- `tests/test_template_contracts.py` — `QUALITY_TEMPLATES` and the new contract tests
- `README.md` — the quality command, `--read-code`, the new artifacts
- `package.json`, `pyproject.toml`, `uv.lock` — version 1.2.0

**Not modified, deliberately:** `templates/shared/viewer.template.html`, `templates/*/code-flow.map.*`. Phase 3a adds a second command; it does not change the first. `report.template.html` and `quality-report.html` are **phase 3b** and must not appear in this phase — if a task seems to need them, stop and report.

**A note on file size.** Claude's map template is 373 lines. The quality template will end near 250. A slash command is one file and cannot be split without changing what gets installed, so keep the additions tight: rules and thresholds, not prose. If a section you are adding runs past ~40 lines, that is a signal to cut words, not to split the file.

---

### Task 1: Install a second command

Everything downstream assumes three quality templates exist and get copied. Build that first, with the templates carrying only their header and argument parsing — enough to be a real installed file, not enough to do analysis yet. Tasks 2-5 fill them in.

**Files:**
- Create: `templates/claude/code-flow.quality.md`
- Create: `templates/gemini/code-flow.quality.toml`
- Create: `templates/copilot/code-flow.quality.prompt.md`
- Modify: `bin/install.js:37-62`
- Modify: `src/code_flow_skill/cli.py:28-40, 53-58, 62-85`
- Modify: `test/install.test.js:26-31`
- Modify: `tests/test_installer_python.py:8-14, 84-107`
- Modify: `tests/test_packaging.py:11-16, 40-45`
- Modify: `package.json:4`, `pyproject.toml:7`, `uv.lock`

**Interfaces:**
- Consumes: nothing.
- Produces: the three template files at the paths above, each containing a `#### 1. Read the Arguments` section (Copilot: `1. **Read the arguments**`). Tasks 2-5 append sections to these files. Also produces the `QUALITY_TEMPLATES` tuple used by every later task's contract tests, and the parity script in Step 8 that every later task re-runs.

- [ ] **Step 1: Write the failing installer tests**

In `test/install.test.js`, replace the `EXPECTED_ALL` constant:

```js
// The exact set `--tool all` must produce — nothing missing, nothing extra.
// Both installers (this one and src/code_flow_skill/cli.py) are asserted
// against the same literal list, which is what keeps them in lockstep.
const EXPECTED_ALL = [
  ".claude/commands/code-flow.map.md",
  ".claude/commands/code-flow.quality.md",
  ".code-flow/viewer.template.html",
  ".gemini/commands/code-flow.map.toml",
  ".gemini/commands/code-flow.quality.toml",
  ".github/prompts/code-flow.map.prompt.md",
  ".github/prompts/code-flow.quality.prompt.md",
];
```

Append three tests to the same file:

```js
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
```

In `tests/test_installer_python.py`, replace `EXPECTED_ALL` with the same seven paths (same comment, same order), and append:

```python
def test_installs_claude_quality_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="claude")
    assert (tmp_path / ".claude" / "commands" / "code-flow.quality.md").is_file()


def test_installs_gemini_quality_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="gemini")
    assert (tmp_path / ".gemini" / "commands" / "code-flow.quality.toml").is_file()


def test_selecting_one_tool_installs_both_of_its_commands(
    tmp_path: Path, run_python_installer
) -> None:
    run_python_installer(tmp_path, tool="copilot")
    prompts = tmp_path / ".github" / "prompts"
    assert (prompts / "code-flow.map.prompt.md").is_file()
    assert (prompts / "code-flow.quality.prompt.md").is_file()
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / ".gemini").exists()
```

Extend the byte-identity map in `test_installed_files_are_byte_identical_to_their_templates` with the three new pairs:

```python
        tmp_path / ".claude" / "commands" / "code-flow.quality.md":
            repo_root / "templates" / "claude" / "code-flow.quality.md",
        tmp_path / ".gemini" / "commands" / "code-flow.quality.toml":
            repo_root / "templates" / "gemini" / "code-flow.quality.toml",
        tmp_path / ".github" / "prompts" / "code-flow.quality.prompt.md":
            repo_root / "templates" / "copilot" / "code-flow.quality.prompt.md",
```

In `tests/test_packaging.py`, extend `EXPECTED_IN_WHEEL`:

```python
EXPECTED_IN_WHEEL = (
    "code_flow_skill/templates/claude/code-flow.map.md",
    "code_flow_skill/templates/claude/code-flow.quality.md",
    "code_flow_skill/templates/gemini/code-flow.map.toml",
    "code_flow_skill/templates/gemini/code-flow.quality.toml",
    "code_flow_skill/templates/copilot/code-flow.map.prompt.md",
    "code_flow_skill/templates/copilot/code-flow.quality.prompt.md",
    "code_flow_skill/templates/shared/viewer.template.html",
)
```

and rewrite the version test — **the version is in the test's name as well as its body**, so both move:

```python
def test_package_versions_match_and_are_1_2_0(repo_root: Path) -> None:
    npm_version = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))["version"]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None, "no version found in pyproject.toml"
    assert npm_version == match.group(1) == "1.2.0"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest -v && npm test`

Expected: FAIL. The Python installer tests fail on the file-set comparison (four paths found, seven expected); `test_package_versions_match_and_are_1_2_0` fails asserting `1.1.0 == "1.2.0"`; `test_wheel_contains_templates` fails listing three missing files; the Node file-set test fails the same way. Nothing errors on import.

- [ ] **Step 3: Create the Claude quality template**

Create `templates/claude/code-flow.quality.md`:

````markdown
---
description: Report DRY, KISS and YAGNI findings from the persisted code-flow map, with file:line evidence and honest coverage.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Code Flow — Quality Report

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, and code that nothing reaches.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

### Instructions

Follow these steps exactly.

#### 1. Read the Arguments

The user's input (`$ARGUMENTS`) carries at most one flag:

- `--read-code` — after deriving candidate findings from the map, open the files
  those candidates cite and confirm each against current source. Off by default.
  It requires the source tree to be present and current, not merely the artifacts
  under `Code_Flows/`.

There is no feature name to parse: this command analyzes the whole map. If the
input contains anything else, say what you read, ignore it, and carry on — do not
treat it as a filter, a path, or a flow name.
````

- [ ] **Step 4: Create the Gemini quality template**

Create `templates/gemini/code-flow.quality.toml`. Everything from `#### 1.` onward must be **byte-identical** to the Claude file — copy it, do not retype it:

```toml
description = "Report DRY, KISS and YAGNI findings from the persisted code-flow map, with file:line evidence and honest coverage."

prompt = '''
## Code Flow — Quality Report

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, and code that nothing reaches.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

### User Input

The user specified: $ARGUMENTS

### Instructions

Follow these steps exactly.

#### 1. Read the Arguments

The user's input (`$ARGUMENTS`) carries at most one flag:

- `--read-code` — after deriving candidate findings from the map, open the files
  those candidates cite and confirm each against current source. Off by default.
  It requires the source tree to be present and current, not merely the artifacts
  under `Code_Flows/`.

There is no feature name to parse: this command analyzes the whole map. If the
input contains anything else, say what you read, ignore it, and carry on — do not
treat it as a filter, a path, or a flow name.
'''
```

Note the two structural differences, both **above** `#### 1.` and therefore outside what the parity script measures: Gemini's `description` is a TOML key rather than YAML frontmatter, and its User Input section is inline prose rather than a fenced block, placed after the title rather than before it. That mirrors exactly how the map templates differ.

- [ ] **Step 5: Create the Copilot quality template**

Create `templates/copilot/code-flow.quality.prompt.md`. Same rules, its own register:

```markdown
---
mode: agent
description: Report DRY, KISS and YAGNI findings from the persisted code-flow map, with file:line evidence and honest coverage.
---

Read the map this project has already written under `Code_Flows/` and report where
it shows duplicated intent, needless complexity, and code that nothing reaches.

This command **never edits source code.** `code-flow.map` adds missing docstrings
as it traces; this one writes documents and stops. Consolidating duplicates and
deleting suspected-dead code carry real blast radius, and that call is the user's.

Follow these steps exactly:

1. **Read the arguments.** At most one flag: `--read-code` — after deriving
   candidate findings from the map, open the files those candidates cite and
   confirm each against current source. Off by default. It requires the source
   tree to be present and current, not merely the artifacts under `Code_Flows/`.
   There is no feature name to parse: this command analyzes the whole map. If the
   input contains anything else, say what you read, ignore it, and carry on — do
   not treat it as a filter, a path, or a flow name.
```

- [ ] **Step 6: Restructure both installers**

In `bin/install.js`, replace the `toolMap` object and the `for` loop that follows it (lines 37-62) with:

```js
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
```

In `src/code_flow_skill/cli.py`, delete `_install_claude`, `_install_gemini` and `_install_copilot` entirely and put this in their place (keep `_install_viewer` exactly as it is):

```python
# Each host installs one file per command. This table and the one in
# bin/install.js must stay in step; the installed-file-set tests in both
# languages are what holds them there.
_TOOL_FILES = {
    "claude": (
        (("claude", "code-flow.map.md"), (".claude", "commands", "code-flow.map.md")),
        (("claude", "code-flow.quality.md"), (".claude", "commands", "code-flow.quality.md")),
    ),
    "gemini": (
        (("gemini", "code-flow.map.toml"), (".gemini", "commands", "code-flow.map.toml")),
        (("gemini", "code-flow.quality.toml"), (".gemini", "commands", "code-flow.quality.toml")),
    ),
    "copilot": (
        (
            ("copilot", "code-flow.map.prompt.md"),
            (".github", "prompts", "code-flow.map.prompt.md"),
        ),
        (
            ("copilot", "code-flow.quality.prompt.md"),
            (".github", "prompts", "code-flow.quality.prompt.md"),
        ),
    ),
}

_TOOL_LABELS = {"claude": "Claude", "gemini": "Gemini", "copilot": "Copilot"}


def _install_tool(target: Path, name: str) -> None:
    """Copy every template belonging to one host into ``target``.

    A plain copy, deliberately: ``shutil.copyfile`` preserves bytes, where a
    text-mode read/write round-trip would translate "\\n" to "\\r\\n" on
    Windows and silently corrupt every shipped template.
    """
    for src_parts, dst_parts in _TOOL_FILES[name]:
        out = target.joinpath(*dst_parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_template_path(*src_parts), out)
        print(f"Installed {_TOOL_LABELS[name]} template: {out}")
```

and replace the dispatch block in `main()`:

```python
    for name in selected:
        _install_tool(target, name)

    _install_viewer(target)
```

- [ ] **Step 7: Bump the version**

Set `"version": "1.2.0"` in `package.json` and `version = "1.2.0"` in `pyproject.toml`.

Then refresh the lockfile so its recorded version matches:

```bash
uv lock
```

Expected: `uv.lock` changes by exactly the one version line. If it wants to change dependency pins as well, stop and report — this phase adds no dependencies.

- [ ] **Step 8: Establish the parity baseline at 0**

Run the Claude/Gemini parity script. Unlike the map templates' script, this one asserts **byte-identity** from `#### 1.` onward, because these are new files with no inherited divergence:

```bash
PYTHONIOENCODING=utf-8 python - <<'PY'
import tomllib, pathlib, difflib
BASELINE = 0  # quality templates are byte-identical from "#### 1." onward
claude = pathlib.Path("templates/claude/code-flow.quality.md").read_text(encoding="utf-8")
gemini = tomllib.loads(pathlib.Path("templates/gemini/code-flow.quality.toml").read_text(encoding="utf-8"))["prompt"]
c = claude[claude.index("#### 1."):].splitlines()
g = gemini[gemini.index("#### 1."):].splitlines()
# autojunk=False is REQUIRED, not a preference. difflib's autojunk heuristic
# activates once a sequence reaches 200 elements and treats any line occurring
# in more than 1% of it as junk — which, in a document this size, means blank
# lines. It then stops matching on them and manufactures phantom divergences.
# `difflib.unified_diff` gives no way to disable it, so this uses
# SequenceMatcher directly. Do not "simplify" this back.
sm = difflib.SequenceMatcher(None, c, g, autojunk=False)
diff = []
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        continue
    diff += ["-" + l for l in c[i1:i2]] + ["+" + l for l in g[j1:j2]]
print(f"divergent lines: {len(diff)} (baseline {BASELINE})")
print("OK" if len(diff) == BASELINE else "DIVERGENCE INTRODUCED")
for l in diff:
    print(l)
PY
```

Expected: `divergent lines: 0 (baseline 0)` and `OK`. Any output beyond that is a divergence this task introduced — fix the templates, do not raise `BASELINE`. Every later task re-runs this script unchanged and expects the same result.

- [ ] **Step 9: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all Python tests pass, including the three new installer tests, the extended file-set and wheel assertions, and the retitled version test. Node goes from 7 to 10 passing. Output pristine — no warnings, no skips.

- [ ] **Step 10: Derive host parity**

Read all three templates end-to-end. Confirm in each host: the no-source-writes rule; `--read-code` described with both its meaning and its requirement that source be present and current; the "no feature name to parse" rule; and the instruction to ignore-and-report unrecognized input rather than treat it as a filter. Record the derivation in the task report.

- [ ] **Step 11: Commit**

```bash
git add templates/claude/code-flow.quality.md templates/gemini/code-flow.quality.toml templates/copilot/code-flow.quality.prompt.md bin/install.js src/code_flow_skill/cli.py test/install.test.js tests/test_installer_python.py tests/test_packaging.py package.json pyproject.toml uv.lock
git commit -m "feat: install code-flow.quality as a second command per host"
```

---

### Task 2: Load the map, and refuse when you cannot

The gating rule is the spine of this command: *a detector that cannot produce its required evidence does not run, and the report names it and says why.* It has to exist before any detector does, or each detector will invent its own answer to "what if the data is missing".

**Files:**
- Modify: `templates/claude/code-flow.quality.md` (append `#### 2.`)
- Modify: `templates/gemini/code-flow.quality.toml` (the same, byte-identical from `#### 1.` onward)
- Modify: `templates/copilot/code-flow.quality.prompt.md` (item 2, its own register)
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: the three templates from Task 1, and `_section_region(text, start, end)` and `_field_reference(field)` from phase 2 (already in `tests/test_template_contracts.py`).
- Produces: the `QUALITY_TEMPLATES` tuple and the region anchors `_LOAD_START` / `_LOAD_END`, both used by Tasks 3-5's tests. Also produces the gating vocabulary — `skipped`, `not run` — that Task 5's report banner renders.

- [ ] **Step 1: Write the failing contract tests**

Append to `tests/test_template_contracts.py`:

```python
QUALITY_TEMPLATES = (
    ("claude", "code-flow.quality.md"),
    ("gemini", "code-flow.quality.toml"),
    ("copilot", "code-flow.quality.prompt.md"),
)

# Marks the start of the "load the map" instructions in every host
# (Claude/Gemini: "#### 2. Load the Map"; Copilot: "2. **Load the map.**").
_LOAD_START = re.compile(r"load the map", re.IGNORECASE)

# Marks the start of the *next* section after it, in every host
# (Claude/Gemini: "#### 3. Run the Detectors"; Copilot: "3. **Run the
# detectors.**"). Used as the end boundary so the scoped region cannot run
# past step 2 into the detector text, where "inventory.json" and "skipped"
# both legitimately appear again.
_LOAD_END = re.compile(r"\n(?:#### 3\.|3\.\s*\*\*Run the detectors)")


def _load_region(text: str) -> str:
    return _section_region(text, _LOAD_START, _LOAD_END)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_reads_all_three_artifact_kinds(
    repo_root: Path, host: str, name: str
) -> None:
    """Every detector's input comes from one of these three, so the load step
    must name all three. A template that forgot `<slug>.json` would produce a
    report with two detectors silently missing."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for artifact in ("index.json", "inventory.json", "<slug>.json"):
        assert artifact in region, f"{host} load step does not name {artifact}"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_stops_when_inventory_is_absent(
    repo_root: Path, host: str, name: str
) -> None:
    """A missing inventory takes two of four detectors with it, so the command
    stops rather than emitting a report whose meaning depends on how the user
    happened to build their map. The remedy must be named, not implied."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "--whole-code-base" in region, f"{host} does not name the remedy"
    assert re.search(r"\bstop\b", region, re.IGNORECASE), f"{host} does not say to stop"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_refuses_to_overwrite_unparsable_artifacts(
    repo_root: Path, host: str, name: str
) -> None:
    """Mirrors the rule the map command already follows for index.json."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"does not parse|cannot parse|fails to parse", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_skips_duplicate_intent_on_thin_maps(
    repo_root: Path, host: str, name: str
) -> None:
    """A thin map carries no snippets, so duplicate-intent has no evidence to
    cite. Both remedies must be named — the flag and the re-map."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "duplicate-intent" in region
    assert "--read-code" in region
    assert re.search(r"--detail\s+standard", region)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_survives_one_bad_flow_file(
    repo_root: Path, host: str, name: str
) -> None:
    """One unreadable flow is a coverage fact, not a stop condition — the other
    flows are still analyzable."""
    region = _load_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"skip that flow|skip it and", region, re.IGNORECASE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: FAIL. Every one of the six fails inside `_section_region` with `template has no section matching 'load the map'` — the assertion in that helper, not a later one. That is the correct failure: the region does not exist yet.

- [ ] **Step 3: Add the canonical block to Claude and Gemini**

Append this to `templates/claude/code-flow.quality.md`, and the byte-identical text to the `prompt` string in `templates/gemini/code-flow.quality.toml`:

````markdown
#### 2. Load the Map

Read three kinds of artifact, in this order. Each detector in step 3 draws on
some of them, and which ones are readable decides which detectors run.

1. `Code_Flows/index.json` — coverage, the file census, and the flow registry.
2. `Code_Flows/inventory.json` — the function catalog.
3. `Code_Flows/<slug>.json` — one per entry in the index's `flows` array.

**The gating rule, which governs everything below:** a detector that cannot
produce its required evidence does not run, and the report names it and says why.
Never substitute a weaker signal for a missing one — a finding derived from
evidence the map does not contain is exactly the confident-wrong finding that
costs more trust than a missing one.

**If `Code_Flows/index.json` is absent**, stop. Tell the user to run
`/code-flow.map` first. There is no map to analyze.

**If `Code_Flows/inventory.json` is absent**, stop. Tell the user to run
`/code-flow.map --whole-code-base` first. Two of the four detectors —
duplicate-intent and unreached — need the catalog and cannot run without it. Do
not fall back to reporting only the other two: half the detectors missing is not
a degraded report, it is a different report, and one whose meaning would change
depending on how the user happened to build their map.

**If `Code_Flows/index.json` or `Code_Flows/inventory.json` exists but does not
parse as JSON**, stop. Report the file path and what is wrong with it, and let the
user repair or delete it. Do not overwrite either file — this command never
writes them, and a file it cannot parse is a file it cannot analyze.

**If a `Code_Flows/<slug>.json` named in the registry is missing or does not
parse**, do not stop. Skip that flow, count it, and report the count with the
coverage banner in step 6. The other flows are still analyzable, and one bad
sidecar is a fact about the map rather than a reason to abandon it.

**If `meta.detail` is `thin` and the user did not pass `--read-code`**, skip the
duplicate-intent detector. A thin map carries no `snippet`, so that detector has
only names, signatures and line counts — not enough to cite the evidence its
findings require. Record it as skipped and name both remedies: re-run with
`--read-code`, or re-map with `/code-flow.map --whole-code-base --detail standard`.
The other three detectors are unaffected and still run.

Note what is *not* a stop condition. `coverage.flowsTraced` below
`coverage.entryPointsFound` means the trace pass never finished, and that is
normal on a large repository. Analyze what was traced and let the banner in step 6
say how much that was.
````

- [ ] **Step 4: Add the same rules to Copilot**

Append to `templates/copilot/code-flow.quality.prompt.md`:

```markdown
2. **Load the map.** Read `Code_Flows/index.json` (coverage, file census, flow
   registry), then `Code_Flows/inventory.json` (the function catalog), then each
   `Code_Flows/<slug>.json` named in the index's `flows` array. **The gating rule,
   which governs everything below:** a detector that cannot produce its required
   evidence does not run, and the report names it and says why — never substitute
   a weaker signal for a missing one. If `index.json` is absent, **stop** and tell
   the user to run `/code-flow.map` first. If `inventory.json` is absent, **stop**
   and tell the user to run `/code-flow.map --whole-code-base` first: duplicate-intent
   and unreached both need the catalog, and reporting only the other two would make
   the report mean something different depending on how the user built their map.
   If either file exists but does not parse as JSON, **stop**, report the path and
   the problem, and do not overwrite it — this command never writes those files. If
   a `<slug>.json` named in the registry is missing or does not parse, do **not**
   stop: skip that flow, count it, and report the count with the coverage banner in
   step 6. If `meta.detail` is `thin` and `--read-code` was not passed, skip the
   duplicate-intent detector — a thin map carries no `snippet` and that detector
   cannot cite the evidence its findings require — and name both remedies: re-run
   with `--read-code`, or re-map with `/code-flow.map --whole-code-base --detail standard`.
   `coverage.flowsTraced` below `coverage.entryPointsFound` is **not** a stop
   condition; it is a partial trace pass, which is normal on a large repository.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: PASS, 18 tests (6 assertions across 3 hosts).

- [ ] **Step 6: Re-run the parity script**

Run the script from Task 1 Step 8 unchanged.

Expected: `divergent lines: 0 (baseline 0)` and `OK`.

- [ ] **Step 7: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all pass. Node unchanged at 10.

- [ ] **Step 8: Derive host parity**

Read all three templates end-to-end. Confirm in each host, by deriving rather than asserting: all three artifact kinds named; both stop conditions with their exact remedies; the do-not-overwrite rule; the skip-one-flow rule; the thin-map skip with both remedies; and the explicit note that partial coverage is not a stop condition. Record the derivation in the task report.

- [ ] **Step 9: Commit**

```bash
git add templates/claude/code-flow.quality.md templates/gemini/code-flow.quality.toml templates/copilot/code-flow.quality.prompt.md tests/test_template_contracts.py
git commit -m "feat: load the map and apply the gating rule"
```

---

### Task 3: The four detectors

The analysis itself. Severity is rule-based throughout — every threshold is a number, so findings cannot drift toward "medium" on vibes.

**Files:**
- Modify: `templates/claude/code-flow.quality.md` (append `#### 3.`)
- Modify: `templates/gemini/code-flow.quality.toml` (the same, byte-identical)
- Modify: `templates/copilot/code-flow.quality.prompt.md` (item 3)
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: `QUALITY_TEMPLATES`, `_section_region`, `_field_reference` from Task 2.
- Produces: the finding schema — the field names `id`, `principle`, `detector`, `severity`, `confidence`, `title`, `rationale`, `sites`, `suggestion`, `effort`, the site fields `file`, `line`, `symbol`, `snippet`, and the per-detector evidence fields `flows`, `metric`, `value`, `exported` — which Task 5 renders and Task 6's fixture instantiates. Also produces the detector names `duplicate-intent`, `repeated-sequence`, `complexity-hotspot`, `unreached`, which Task 6's `DETECTORS` set repeats. Tasks 4 and 5 define their own region anchors; `_DETECTORS_END` is the only one they must not collide with.

- [ ] **Step 1: Write the failing contract tests**

Append to `tests/test_template_contracts.py`:

```python
# Marks the start of the detector instructions in every host (Claude/Gemini:
# "#### 3. Run the Detectors"; Copilot: "3. **Run the detectors.**").
_DETECTORS_START = re.compile(r"run the detectors", re.IGNORECASE)

# Marks the start of the *next* section (Claude/Gemini: "#### 4. Verify";
# Copilot: "4. **Verify"). Scoping matters here: "snippet", "severity" and
# "sites" all appear again in the step 5/6 output instructions, so an
# unscoped search would pass even with the detector rules deleted.
_DETECTORS_END = re.compile(r"\n(?:#### 4\.|4\.\s*\*\*Verify)")

DETECTOR_NAMES = (
    "duplicate-intent",
    "repeated-sequence",
    "complexity-hotspot",
    "unreached",
)

FINDING_FIELD_NAMES = (
    "id",
    "principle",
    "detector",
    "severity",
    "confidence",
    "title",
    "rationale",
    "sites",
    "suggestion",
    "effort",
)


def _detectors_region(text: str) -> str:
    return _section_region(text, _DETECTORS_START, _DETECTORS_END)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_all_four_detectors(
    repo_root: Path, host: str, name: str
) -> None:
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for detector in DETECTOR_NAMES:
        assert detector in region, f"{host} detector step does not name {detector}"


# Each threshold, tied to the concept it governs. A bare number search would
# be vacuous — "8" and "6" and "2" all occur incidentally in a region this
# size — so every pattern requires the number adjacent to what it measures.
# The patterns are deliberately loose about the words *between* number and
# concept, because Claude/Gemini say "fan-out is at least 8" where Copilot's
# numbered-list register says "at fan-out 8", and both are correct.
SEVERITY_THRESHOLDS = (
    r"3 sites",
    r"40 (?:duplicated )?lines",
    r"3 consecutive calls",
    r"2 (?:different )?flows",
    r"fan-out.{0,20}\b8\b",
    r"depth.{0,20}\b6\b",
    r"`loc`.{0,20}\b120\b",
)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_states_every_severity_threshold(
    repo_root: Path, host: str, name: str
) -> None:
    """Severity is rule-based, not impressionistic. A template that dropped a
    threshold would leave the assistant to invent one, and findings would drift
    toward medium. Every number from the design must survive in every host."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for pattern in SEVERITY_THRESHOLDS:
        assert re.search(pattern, region), f"{host} is missing threshold {pattern!r}"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_every_finding_field(
    repo_root: Path, host: str, name: str
) -> None:
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in FINDING_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host} detector step never references the finding field {field!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_the_per_detector_evidence_fields(
    repo_root: Path, host: str, name: str
) -> None:
    """Three detectors are told to cite evidence the core schema has no home
    for — flow slugs, the metric that tripped and its value, export status. If
    the schema does not name those fields, each run invents its own key for
    them and the report JSON stops being a stable shape."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in ("flows", "metric", "value", "exported"):
        assert _field_reference(field).search(region), (
            f"{host} never names the evidence field {field!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_separates_test_only_reachability(
    repo_root: Path, host: str, name: str
) -> None:
    """Excluding tests would make every test-only helper look dead. The design
    splits the outcome in two rather than collapsing it."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "production-unreached" in region
    assert "kept alive only by its own tests" in region


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_caps_exported_and_never_instructs_deletion(
    repo_root: Path, host: str, name: str
) -> None:
    """Parser-free tracing cannot see dynamic dispatch, so unreached is a
    candidate and never a verdict."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "confirm before deleting" in region
    assert re.search(r"`exported`.{0,120}\blow\b", region, re.IGNORECASE | re.DOTALL)
    assert re.search(r"never instructs? deletion|do not tell the user to delete", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_clusters_rather_than_pairs(
    repo_root: Path, host: str, name: str
) -> None:
    """Three copies of one helper is one finding with three sites, not three
    pairwise findings. Without this rule a 5-site cluster becomes 10 findings."""
    region = _detectors_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"never (one finding )?per pair|not pairwise", region, re.IGNORECASE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: the seven new assertions fail with `template has no section matching 'run the detectors'`. Task 2's six still pass.

- [ ] **Step 3: Add the canonical block to Claude and Gemini**

Append this to `templates/claude/code-flow.quality.md`, and byte-identically to the Gemini `prompt` string:

````markdown
#### 3. Run the Detectors

Four detectors. Step 2's gating rule has already decided which of them run; run
those, and only those.

Every severity below is a **rule**, not a judgement. Apply the number. If a
finding does not clear a threshold, it is not a finding of lower severity — it is
not a finding.

**a. duplicate-intent (DRY).** Cluster catalogued functions that do the same work
under different names or in different places. Compare `purpose` and `signature`
across the whole inventory, and `snippet` wherever the map carries one. Severity
is `high` when a cluster has at least 3 sites, or when the duplicated code totals
at least 40 lines; otherwise `medium`. Cite every site, with its snippet.

**b. repeated-sequence (DRY).** Across the flow graphs, find chains of at least
3 consecutive calls that appear in at least 2 different flows. Severity is `high`
at that threshold; a shorter chain, or one appearing in only 1 flow, is not a
finding. Cite the shared subpath and the `slug` of every flow it appears in.

**c. complexity-hotspot (KISS).** For each node across the flow graphs, take its
fan-out (its count of outbound edges) and its depth (its distance from that flow's
`entry` node). Severity is `high` when fan-out is at least 8, or depth is at least
6, or the function's `loc` is at least 120; otherwise `medium`. Cite the metric
that tripped and its value.

**d. unreached (YAGNI).** Subtract. Every inventory `id` that appears as a node
`id` in any flow is reached; what remains is not. The join is exact — the map
derives both ids by the same rule — so do not match on names. Then split what
remains by `role`:

- A `role` of `test` is never a finding. A test helper reached only by tests is
  doing its job.
- A `role` of `source` reached by no flow and by no test file is `unreached`: a
  dead-code candidate.
- A `role` of `source` reached only from test files is `production-unreached`.
  Phrase it "kept alive only by its own tests" and never rate it `high`.

Severity is `high` only when the entry is `unreached`, is not `exported`, and is
not test-only. Anything whose `exported` is true is capped at `low`, because a
public API surface has callers this repository cannot see.

**unreached is a candidate, never a verdict.** Tracing here is search and reading,
not a compiler's view: it cannot see reflection, `getattr`, dependency injection,
framework hooks, decorator registration, or entry points declared in
configuration. Phrase every one of these findings as "not reached by any of the N
mapped flows — confirm before deleting", with N the number of flows actually
analyzed. The report never instructs deletion.

**One cluster, one finding.** Sites belonging to the same cluster produce a single
finding carrying several `sites` — never one finding per pair. Three copies of a
helper is one finding with three sites, not three findings.

**Emit each finding in this shape:**

```json
{
  "id": "DRY-01",
  "principle": "DRY",
  "detector": "duplicate-intent",
  "severity": "high",
  "confidence": "unverified",
  "title": "Email validation implemented in 3 places",
  "rationale": "Three functions independently validate email format with equivalent logic.",
  "sites": [
    { "file": "src/auth/validators.py", "line": 12, "symbol": "validate_email",
      "snippet": "def validate_email(value):\n    ..." }
  ],
  "suggestion": "Consolidate into one helper and have the other two call it.",
  "effort": "small"
}
```

`principle` is `DRY`, `KISS` or `YAGNI`. `severity` is `high`, `medium` or `low`.
`confidence` is `unverified` unless step 4 verified the finding. `effort` is
`small`, `medium` or `large`. `id` is the principle, a hyphen, and a two-digit
counter that restarts per principle in emission order: `DRY-01`, `DRY-02`,
`KISS-01`, `YAGNI-01`. Ids must be stable within the run, because the markdown and
the JSON cross-reference each other by them.

Three detectors carry evidence the fields above have no home for. Add exactly
these, and nothing else:

- `repeated-sequence` adds `flows` — the array of flow `slug`s the chain appears in.
- `complexity-hotspot` adds `metric` (`fan-out`, `depth` or `loc`) and `value`.
- `unreached` adds `exported`, copied from the inventory entry.
````

- [ ] **Step 4: Add the same rules to Copilot**

Append to `templates/copilot/code-flow.quality.prompt.md`:

````markdown
3. **Run the detectors.** Four of them; step 2's gating rule already decided which
   run. Every severity is a **rule**, not a judgement — apply the number, and if a
   finding does not clear a threshold it is not a finding at all.
   - **duplicate-intent (DRY)** — cluster catalogued functions doing the same work
     under different names or places, comparing `purpose`, `signature`, and
     `snippet` wherever the map carries one. `high` at 3 sites or 40 duplicated
     lines; otherwise `medium`. Cite every site with its snippet.
   - **repeated-sequence (DRY)** — chains of at least 3 consecutive calls appearing
     in at least 2 flows. `high` at that threshold; shorter or rarer is not a
     finding. Cite the shared subpath and every flow `slug` it appears in.
   - **complexity-hotspot (KISS)** — per node, fan-out (outbound edges) and depth
     (distance from that flow's `entry`). `high` at fan-out 8, depth 6, or `loc`
     120; otherwise `medium`. Cite the metric that tripped and its value.
   - **unreached (YAGNI)** — subtract: every inventory `id` appearing as a node
     `id` in any flow is reached, and the join is exact because the map derives
     both by the same rule, so do not match on names. A `role` of `test` is never
     a finding. A `role` of `source` reached by no flow and no test is `unreached`.
     A `role` of `source` reached only from test files is `production-unreached` —
     phrase it "kept alive only by its own tests" and never rate it `high`.
     `high` only when `unreached`, not `exported`, and not test-only; anything
     whose `exported` is true is capped at `low`, because a public API surface has
     callers this repository cannot see.

   **unreached is a candidate, never a verdict.** Tracing is search and reading,
   not a compiler's view: it cannot see reflection, `getattr`, dependency
   injection, framework hooks, decorator registration, or entry points declared in
   configuration. Phrase each as "not reached by any of the N mapped flows —
   confirm before deleting", N being the flows actually analyzed. The report never
   instructs deletion.

   **One cluster, one finding** — several `sites` on one finding, never one finding
   per pair. Three copies of a helper is one finding with three sites.

   Emit each finding in this shape:

   ```json
   {
     "id": "DRY-01",
     "principle": "DRY",
     "detector": "duplicate-intent",
     "severity": "high",
     "confidence": "unverified",
     "title": "Email validation implemented in 3 places",
     "rationale": "Three functions independently validate email format with equivalent logic.",
     "sites": [
       { "file": "src/auth/validators.py", "line": 12, "symbol": "validate_email",
         "snippet": "def validate_email(value):\n    ..." }
     ],
     "suggestion": "Consolidate into one helper and have the other two call it.",
     "effort": "small"
   }
   ```

   `principle` is `DRY`, `KISS` or `YAGNI`; `severity` is `high`, `medium` or
   `low`; `confidence` is `unverified` unless step 4 verified it; `effort` is
   `small`, `medium` or `large`. `id` is the principle, a hyphen, and a two-digit
   counter restarting per principle in emission order. Ids must be stable within
   the run — the markdown and the JSON cross-reference each other by them.

   Three detectors carry evidence those fields have no home for. Add exactly
   these, and nothing else: `repeated-sequence` adds `flows` (the array of flow
   `slug`s the chain appears in); `complexity-hotspot` adds `metric` (`fan-out`,
   `depth` or `loc`) and `value`; `unreached` adds `exported`, copied from the
   inventory entry.
````

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: PASS, 39 tests (13 assertions across 3 hosts).

- [ ] **Step 6: Re-run the parity script**

Run the script from Task 1 Step 8 unchanged. Expected: `0` and `OK`.

The JSON example is the first fenced block in this file. Confirm it is a **three**-backtick fence in both hosts — the block contains no nested fence, so Claude does not need four, and using four would put this task's baseline above 0.

- [ ] **Step 7: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all pass. Node unchanged at 10.

- [ ] **Step 8: Derive host parity**

Read all three templates end-to-end. Confirm in each host: all four detector names; all seven threshold numbers (3 sites, 40 lines, 3 calls, 2 flows, fan-out 8, depth 6, loc 120); the exact-`id`-join rule and the instruction not to match on names; the three-way `role` split; the `exported` cap; the candidate-never-verdict phrasing including "confirm before deleting"; the one-cluster-one-finding rule; every field of the finding schema; and the three per-detector evidence fields (`flows`, `metric`/`value`, `exported`) with the instruction to add those and nothing else. Record the derivation in the task report.

- [ ] **Step 9: Commit**

```bash
git add templates/claude/code-flow.quality.md templates/gemini/code-flow.quality.toml templates/copilot/code-flow.quality.prompt.md tests/test_template_contracts.py
git commit -m "feat: the four detectors, with rule-based severity"
```

---

### Task 4: `--read-code` verification, and what staleness does

The feature's main defense against false positives, plus the one interaction the design had to resolve explicitly: verification and the staleness drop-rule pull in opposite directions, and verification wins.

**Files:**
- Modify: `templates/claude/code-flow.quality.md` (append `#### 4.`)
- Modify: `templates/gemini/code-flow.quality.toml` (the same, byte-identical)
- Modify: `templates/copilot/code-flow.quality.prompt.md` (item 4)
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: `QUALITY_TEMPLATES`, `_section_region`, and the `confidence` field from Task 3.
- Produces: the `verified` / `unverified` values Task 5's banner counts, and the `filesChanged` / `findingsDropped` counts Task 5 renders.

- [ ] **Step 1: Write the failing contract tests**

Append to `tests/test_template_contracts.py`:

```python
# Marks the start of the verification instructions (Claude/Gemini: "#### 4.
# Verify Against Source"; Copilot: "4. **Verify against source.**").
_VERIFY_START = re.compile(r"verify against source", re.IGNORECASE)

# Marks the start of the *next* section (Claude/Gemini: "#### 5. Write";
# Copilot: "5. **Write"). Needed because "verified" and "stale" both recur in
# the step 6 banner text.
_VERIFY_END = re.compile(r"\n(?:#### 5\.|5\.\s*\*\*Write)")


def _verify_region(text: str) -> str:
    return _section_region(text, _VERIFY_START, _VERIFY_END)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_verifies_only_cited_files(
    repo_root: Path, host: str, name: str
) -> None:
    """--read-code verifies candidates; it does not re-scan the repository.
    Re-scanning would duplicate the cost of mapping and not fit on a large
    codebase, which is the whole reason the map is persisted."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"only the files", region, re.IGNORECASE)
    assert re.search(r"not a second scan|do not re-?scan", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_marks_confidence_both_ways(
    repo_root: Path, host: str, name: str
) -> None:
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "verified" in region
    assert "unverified" in region


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_drops_only_unverified_stale_findings(
    repo_root: Path, host: str, name: str
) -> None:
    """The order is verify-then-drop. --read-code reads current source, so a
    finding it confirms was checked against the very change that made the file
    stale; dropping it afterwards would discard the best evidence in the
    report."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"unverified", region)
    assert re.search(r"hash", region, re.IGNORECASE)
    assert re.search(r"verify first|before dropping|then drop", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_corrects_line_numbers_on_verified_findings(
    repo_root: Path, host: str, name: str
) -> None:
    """A finding kept through a file change must cite where the code is now,
    not where the map recorded it."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"correct.{0,40}line", region, re.IGNORECASE | re.DOTALL)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_never_stops_on_staleness(
    repo_root: Path, host: str, name: str
) -> None:
    """There is no staleness threshold, because any threshold would be a number
    the design cannot justify."""
    region = _verify_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"never a reason to stop|does not stop the command", region, re.IGNORECASE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: the five new assertions fail with `template has no section matching 'verify against source'`. Tasks 2 and 3's thirteen still pass.

- [ ] **Step 3: Add the canonical block to Claude and Gemini**

Append this to `templates/claude/code-flow.quality.md`, and byte-identically to the Gemini `prompt` string:

````markdown
#### 4. Verify Against Source

Two things happen here, and their order matters.

**a. Check staleness.** For every file cited by any candidate finding, compare the
file's current content against the `hash` recorded for it in `index.json`'s
`files` array. Count how many mapped files no longer match; that count goes in the
banner in step 6.

Staleness is **never a reason to stop the command**. There is no threshold — any
threshold would be a number this design cannot justify.

**b. Verify, if `--read-code` was passed.** This verifies candidates; it is **not
a second scan of the repository**. Do not re-scan: scanning everything again would
duplicate the cost of mapping and would not fit on a large codebase, which is the
reason the map is persisted in the first place.

1. Open **only the files the candidate findings cite**. Nothing else.
2. Confirm or drop each candidate against real current source.
3. For each candidate that survives, set its `confidence` to `verified` and
   **correct its sites' `line` numbers to where the code is now**.
4. For each candidate that does not survive, drop it.

Without `--read-code`, every finding keeps `confidence: "unverified"`.

**c. Drop what is left stale and unverified.** Verify first, then drop. Any
finding still marked `unverified` whose `sites` cite a file whose `hash` no longer
matches is dropped, and counted for the banner. Its `file:line` evidence is known
to be wrong, and `file:line` evidence is the whole currency of this report.

A `verified` finding is never dropped for staleness. `--read-code` read current
source, so such a finding was confirmed against the very change that made the file
stale — dropping it would discard the best evidence in the report. This is what
the flag buys: it turns staleness from a reason to discard findings into a reason
to re-check them, and under `--read-code` the dropped count is usually zero.
````

- [ ] **Step 4: Add the same rules to Copilot**

Append to `templates/copilot/code-flow.quality.prompt.md`:

```markdown
4. **Verify against source.** Two things, and their order matters.
   - **Check staleness.** For every file cited by a candidate finding, compare its
     current content against the `hash` recorded in `index.json`'s `files` array,
     and count how many mapped files no longer match — that count goes in the step 6
     banner. Staleness is **never a reason to stop the command**; there is no
     threshold, because any threshold would be a number this design cannot justify.
   - **Verify, if `--read-code` was passed.** This verifies candidates and is **not
     a second scan of the repository** — do not re-scan, since scanning everything
     again would duplicate the cost of mapping and not fit on a large codebase.
     Open **only the files the candidate findings cite**, confirm or drop each
     against real current source, set surviving candidates' `confidence` to
     `verified` and **correct their sites' `line` numbers to where the code is
     now**, and drop the rest. Without the flag every finding stays `unverified`.
   - **Drop what is left stale and unverified.** Verify first, then drop: any
     finding still `unverified` whose `sites` cite a file whose `hash` no longer
     matches is dropped and counted for the banner, because its `file:line`
     evidence is known wrong and `file:line` evidence is this report's whole
     currency. A `verified` finding is **never** dropped for staleness — it was
     confirmed against the very change that made the file stale, so dropping it
     would discard the best evidence in the report. Under `--read-code` the dropped
     count is usually zero.
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: PASS, 54 tests (18 assertions across 3 hosts).

- [ ] **Step 6: Re-run the parity script**

Run the script from Task 1 Step 8 unchanged. Expected: `0` and `OK`.

- [ ] **Step 7: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all pass. Node unchanged at 10.

- [ ] **Step 8: Derive host parity**

Read all three templates end-to-end. Confirm in each host: verify-only-cited-files with the explicit not-a-rescan rule; both `confidence` values; line-number correction on verified findings; verify-before-drop ordering; that `verified` findings are never dropped for staleness and why; and that staleness never stops the command. Record the derivation in the task report.

- [ ] **Step 9: Commit**

```bash
git add templates/claude/code-flow.quality.md templates/gemini/code-flow.quality.toml templates/copilot/code-flow.quality.prompt.md tests/test_template_contracts.py
git commit -m "feat: --read-code verification, and verify-before-drop on stale files"
```

---

### Task 5: Write the two reports

The outputs. JSON first, markdown rendered from it — the same data-then-presentation shape the map side already has, and what lets phase 3b add a third rendering without touching any analysis.

**Files:**
- Modify: `templates/claude/code-flow.quality.md` (append `#### 5.` and `#### 6.`)
- Modify: `templates/gemini/code-flow.quality.toml` (the same, byte-identical)
- Modify: `templates/copilot/code-flow.quality.prompt.md` (items 5 and 6)
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: `QUALITY_TEMPLATES` from Task 2, `_section_region` and `_field_reference` from phase 1, and the `verified`/`unverified` vocabulary plus the `filesChanged`/`findingsDropped` counts from Task 4.
- Produces: the `quality-report.json` top-level shape — `schema`, `meta`, `coverage`, `findings` — which Task 6's fixture instantiates and phase 3b's viewer consumes.

- [ ] **Step 1: Write the failing contract tests**

Append to `tests/test_template_contracts.py`:

```python
# Marks the start of the output instructions (Claude/Gemini: "#### 5. Write
# the Report Data"; Copilot: "5. **Write the report data.**"). Runs to the
# end of the template, so no end anchor is needed — but one is supplied
# anyway so a future step 7 cannot silently widen the region.
_OUTPUT_START = re.compile(r"write the report data", re.IGNORECASE)
_OUTPUT_END = re.compile(r"\n(?:#### 7\.|7\.\s*\*\*)")

REPORT_FIELD_NAMES = ("schema", "meta", "coverage", "findings")


def _output_region(text: str) -> str:
    return _section_region(text, _OUTPUT_START, _OUTPUT_END)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_writes_both_artifacts(
    repo_root: Path, host: str, name: str
) -> None:
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "quality-report.json" in region
    assert "quality-report.md" in region


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_writes_json_before_markdown(
    repo_root: Path, host: str, name: str
) -> None:
    """The JSON is the data and the markdown is one rendering of it. Writing
    the markdown first would make them two independent transcriptions that can
    disagree — and phase 3b adds a third rendering off the same JSON."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert region.index("quality-report.json") < region.index("quality-report.md")


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_names_every_report_field(
    repo_root: Path, host: str, name: str
) -> None:
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in REPORT_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host} output step never references the report field {field!r}"
        )


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_leads_with_coverage(
    repo_root: Path, host: str, name: str
) -> None:
    """Honesty rule 2: a clean section under partial coverage means clean
    within what was mapped, and the document must say so in words."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert "clean within what was mapped" in region
    assert re.search(r"flowsTraced", region)
    assert re.search(r"entryPointsFound", region)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_banners_skips_and_drops(
    repo_root: Path, host: str, name: str
) -> None:
    """Everything the gating rule and the drop-rule suppressed has to surface,
    or the report reads as complete when it is not."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    for field in ("filesChanged", "findingsDropped", "detectorsSkipped", "flowsUnreadable"):
        assert _field_reference(field).search(region), f"{host} banner omits {field!r}"


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_orders_findings_deterministically(
    repo_root: Path, host: str, name: str
) -> None:
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"severity.{0,80}site count.{0,80}principle", region, re.IGNORECASE | re.DOTALL)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_reports_when_there_are_no_findings(
    repo_root: Path, host: str, name: str
) -> None:
    """An empty report is a real report, not a skipped one — and never a clean
    bill of health."""
    region = _output_region((repo_root / "templates" / host / name).read_text(encoding="utf-8"))
    assert re.search(r"no findings", region, re.IGNORECASE)
    assert re.search(r"clean bill of health", region, re.IGNORECASE)


@pytest.mark.parametrize("host,name", QUALITY_TEMPLATES)
def test_quality_template_never_writes_source(
    repo_root: Path, host: str, name: str
) -> None:
    """Checked over the whole template, not a region: this rule belongs
    everywhere and its absence anywhere is the defect."""
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert re.search(r"never edits source code", text, re.IGNORECASE)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: seven of the eight new assertions fail with `template has no section matching 'write the report data'`. The eighth is the exception noted below. `test_quality_template_never_writes_source` **passes already** — Task 1 put that sentence in the header of all three templates. That is correct and not a reason to change anything.

- [ ] **Step 3: Add the canonical block to Claude and Gemini**

Append this to `templates/claude/code-flow.quality.md`, and byte-identically to the Gemini `prompt` string:

````markdown
#### 5. Write the Report Data

Write `Code_Flows/quality-report.json` first. It is the data; step 6's markdown is
one rendering of it, and writing the markdown first would make them two
independent transcriptions free to disagree.

Order the `findings` array by `severity` descending (`high`, `medium`, `low`),
then by site count descending, then by `principle`. That order is what the ids
assigned in step 3 must already reflect.

```json
{
  "schema": 1,
  "meta": {
    "root": "C:/Users/example/project",
    "generated": "2026-08-07",
    "readCode": false,
    "mapGenerated": "2026-08-06",
    "mapMode": "whole-code-base",
    "mapDetail": "standard"
  },
  "coverage": {
    "flowsTraced": 14,
    "entryPointsFound": 17,
    "functionsCatalogued": 1180,
    "flowsUnreadable": 0,
    "filesChanged": 6,
    "findingsDropped": 2,
    "detectorsSkipped": ["duplicate-intent"]
  },
  "findings": []
}
```

`meta.root` is the one absolute path in the file; every path inside `findings`
is repo-relative with forward slashes. `mapGenerated`, `mapMode` and `mapDetail`
are copied from the map's own `index.json` `meta`, so the report records which map
it read. `detectorsSkipped` lists detector names step 2 gated off, and is an empty
array when all four ran.

#### 6. Write the Report

Render `Code_Flows/quality-report.md` from the JSON you just wrote. Nothing in it
may contradict that file.

**Lead with coverage — this is a requirement, not a formatting preference.** The
first thing under the title is a banner stating: how many of `entryPointsFound`
entry points were traced (`flowsTraced`), how many functions were catalogued, how
many flows were unreadable, how many mapped files have changed since mapping, how
many findings were dropped as stale, and which detectors were skipped and why.

If `flowsTraced` is below `entryPointsFound`, say in words that the map is partial
and that every section below is **clean within what was mapped** — never a clean
bill of health for the repository.

Then a summary count by principle and severity. Then the findings grouped by
principle, each rendering its `id`, `title`, `severity`, `confidence`, `rationale`,
a sites table of `file:line` and `symbol`, its `suggestion`, and its `effort`.

**If there are no findings, still write the report.** Say there were no findings,
and repeat the coverage banner immediately after — an empty report under partial
coverage means the mapped portion was clean, and the document must say that rather
than implying a clean bill of health.

Say **"catalogued"**, never "all". The map came from search and reading, not an
AST walk, so it is best-effort and the report must never claim completeness.

Finally, report both file paths to the user, along with the coverage numbers and
the count of findings by severity.
````

- [ ] **Step 4: Add the same rules to Copilot**

Append to `templates/copilot/code-flow.quality.prompt.md`:

````markdown
5. **Write the report data.** Write `Code_Flows/quality-report.json` **first** — it
   is the data, and step 6's markdown is one rendering of it; writing the markdown
   first would make them two independent transcriptions free to disagree. Order
   `findings` by `severity` descending (`high`, `medium`, `low`), then site count
   descending, then `principle` — the order the step 3 ids must already reflect.

   ```json
   {
     "schema": 1,
     "meta": {
       "root": "C:/Users/example/project",
       "generated": "2026-08-07",
       "readCode": false,
       "mapGenerated": "2026-08-06",
       "mapMode": "whole-code-base",
       "mapDetail": "standard"
     },
     "coverage": {
       "flowsTraced": 14,
       "entryPointsFound": 17,
       "functionsCatalogued": 1180,
       "flowsUnreadable": 0,
       "filesChanged": 6,
       "findingsDropped": 2,
       "detectorsSkipped": ["duplicate-intent"]
     },
     "findings": []
   }
   ```

   `meta.root` is the one absolute path; every path inside `findings` is
   repo-relative with forward slashes. `mapGenerated`, `mapMode` and `mapDetail`
   are copied from the map's own `index.json` `meta`, so the report records which
   map it read. `detectorsSkipped` lists the detectors step 2 gated off, and is an
   empty array when all four ran.

6. **Write the report.** Render `Code_Flows/quality-report.md` from that JSON;
   nothing in it may contradict that file. **Lead with coverage — a requirement,
   not a formatting preference:** the first thing under the title states how many
   of `entryPointsFound` entry points were traced (`flowsTraced`), how many
   functions were catalogued, how many flows were unreadable, how many mapped files
   have changed since mapping, how many findings were dropped as stale, and which
   detectors were skipped and why. If `flowsTraced` is below `entryPointsFound`,
   say in words that the map is partial and that everything below is **clean within
   what was mapped** — never a clean bill of health for the repository. Then a
   summary count by principle and severity, then findings grouped by principle,
   each rendering `id`, `title`, `severity`, `confidence`, `rationale`, a sites
   table of `file:line` and `symbol`, `suggestion`, and `effort`. **If there are no
   findings, still write the report:** say so and repeat the coverage banner
   immediately after, because an empty report under partial coverage means the
   mapped portion was clean and must not imply a clean bill of health. Say
   **"catalogued"**, never "all" — the map came from search and reading, not an AST
   walk. Finally, report both file paths to the user with the coverage numbers and
   the count of findings by severity.
````

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v -k quality`

Expected: PASS, 78 tests (26 assertions across 3 hosts).

- [ ] **Step 6: Re-run the parity script**

Run the script from Task 1 Step 8 unchanged. Expected: `0` and `OK`.

- [ ] **Step 7: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all pass. Node unchanged at 10.

- [ ] **Step 8: Derive host parity**

Read all three templates end-to-end. Confirm in each host: both output paths with JSON named before markdown; every top-level report field; every banner field; the coverage-leads rule with the "clean within what was mapped" phrasing; the deterministic ordering; the no-findings rule with its "clean bill of health" caveat; and "catalogued" rather than "all". Record the derivation in the task report.

- [ ] **Step 9: Commit**

```bash
git add templates/claude/code-flow.quality.md templates/gemini/code-flow.quality.toml templates/copilot/code-flow.quality.prompt.md tests/test_template_contracts.py
git commit -m "feat: write quality-report.json and render the markdown from it"
```

---

### Task 6: Make the finding schema executable, and document the command

The finding schema is prose in three templates, which means nothing checks that anything obeys it. `tests/test_node_ids.py` solved exactly this problem for the node `id` rule in phase 2; do the same here. Then document the command and close the phase.

**Files:**
- Create: `examples/sample-report.json`
- Create: `tests/test_report_schema.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `FINDING_FIELD_NAMES` and the detector names from Task 3; the report shape from Task 5.
- Produces: nothing later tasks depend on. This is the last task of phase 3a.

- [ ] **Step 1: Write the failing test**

Create `tests/test_report_schema.py`:

```python
"""The quality report's finding schema, made executable.

The schema is prose in three prompt templates, which means nothing checks that
anything obeys it — including the fixture this repository ships. This module
implements the constraints once and asserts the fixture meets them, so a change
to the schema that the fixture contradicts fails the suite instead of shipping.

This is the same move `tests/test_node_ids.py` makes for the node `id` rule,
and for the same reason: a contract that lives only in prompt prose is a
contract nothing enforces.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PRINCIPLES = {"DRY", "KISS", "YAGNI"}
SEVERITIES = {"high", "medium", "low"}
CONFIDENCES = {"verified", "unverified"}
EFFORTS = {"small", "medium", "large"}
DETECTORS = {
    "duplicate-intent",
    "repeated-sequence",
    "complexity-hotspot",
    "unreached",
}
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

_ID = re.compile(r"^(DRY|KISS|YAGNI)-\d{2}$")


@pytest.fixture
def report(repo_root: Path) -> dict:
    return json.loads((repo_root / "examples" / "sample-report.json").read_text(encoding="utf-8"))


def test_report_has_the_four_top_level_keys(report: dict) -> None:
    assert set(report) == {"schema", "meta", "coverage", "findings"}
    assert report["schema"] == 1


def test_coverage_carries_every_banner_number(report: dict) -> None:
    """Step 6's banner renders each of these. A fixture missing one would let a
    template drop it without any test noticing."""
    assert set(report["coverage"]) == {
        "flowsTraced",
        "entryPointsFound",
        "functionsCatalogued",
        "flowsUnreadable",
        "filesChanged",
        "findingsDropped",
        "detectorsSkipped",
    }


def test_findings_use_only_permitted_enum_values(report: dict) -> None:
    for finding in report["findings"]:
        assert finding["principle"] in PRINCIPLES
        assert finding["detector"] in DETECTORS
        assert finding["severity"] in SEVERITIES
        assert finding["confidence"] in CONFIDENCES
        assert finding["effort"] in EFFORTS


def test_finding_ids_match_their_principle_and_are_unique(report: dict) -> None:
    seen = set()
    for finding in report["findings"]:
        assert _ID.match(finding["id"]), f"malformed id {finding['id']!r}"
        assert finding["id"].split("-")[0] == finding["principle"]
        assert finding["id"] not in seen, f"duplicate id {finding['id']!r}"
        seen.add(finding["id"])


def test_every_finding_carries_at_least_one_site(report: dict) -> None:
    """A finding without a site cites no evidence, and file:line evidence is
    the whole currency of this report."""
    for finding in report["findings"]:
        assert finding["sites"], f"{finding['id']} has no sites"
        for site in finding["sites"]:
            assert site["file"] and not site["file"].startswith("/")
            assert "\\" not in site["file"], "paths use forward slashes"
            assert isinstance(site["line"], int) and site["line"] > 0
            assert site["symbol"]


def test_findings_are_ordered_by_severity_then_site_count(report: dict) -> None:
    keys = [
        (SEVERITY_RANK[f["severity"]], -len(f["sites"]))
        for f in report["findings"]
    ]
    assert keys == sorted(keys), "findings are not in the documented order"


def test_exported_unreached_findings_are_capped_at_low(report: dict) -> None:
    """A public API surface has callers this repository cannot see, so an
    exported symbol never reaches high severity."""
    for finding in report["findings"]:
        if finding["detector"] == "unreached" and finding.get("exported"):
            assert finding["severity"] == "low"


def test_unreached_findings_never_instruct_deletion(report: dict) -> None:
    """Parser-free tracing cannot see dynamic dispatch, so these are candidates
    and never verdicts."""
    for finding in report["findings"]:
        if finding["detector"] == "unreached":
            assert "confirm before deleting" in finding["rationale"].lower()
            assert "delete " not in finding["suggestion"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --group dev pytest tests/test_report_schema.py -v`

Expected: FAIL — every test errors in the `report` fixture with `FileNotFoundError` for `examples/sample-report.json`.

- [ ] **Step 3: Create the fixture**

Create `examples/sample-report.json`. It carries one finding per detector, so every enum value and every rule above is exercised by something:

```json
{
  "schema": 1,
  "meta": {
    "root": "C:/Users/example/project",
    "generated": "2026-08-07",
    "readCode": true,
    "mapGenerated": "2026-08-06",
    "mapMode": "whole-code-base",
    "mapDetail": "standard"
  },
  "coverage": {
    "flowsTraced": 14,
    "entryPointsFound": 17,
    "functionsCatalogued": 1180,
    "flowsUnreadable": 0,
    "filesChanged": 6,
    "findingsDropped": 2,
    "detectorsSkipped": []
  },
  "findings": [
    {
      "id": "DRY-01",
      "principle": "DRY",
      "detector": "duplicate-intent",
      "severity": "high",
      "confidence": "verified",
      "title": "Email validation implemented in 3 places",
      "rationale": "Three functions independently validate email format with equivalent logic.",
      "sites": [
        { "file": "src/auth/validators.py", "line": 12, "symbol": "validate_email",
          "snippet": "def validate_email(value):\n    return bool(EMAIL_RE.match(value))" },
        { "file": "src/api/schemas.py", "line": 48, "symbol": "check_email",
          "snippet": "def check_email(raw):\n    return EMAIL_PATTERN.fullmatch(raw) is not None" },
        { "file": "src/admin/forms.py", "line": 91, "symbol": "is_valid_email",
          "snippet": "def is_valid_email(s):\n    return re.match(r'[^@]+@[^@]+', s) is not None" }
      ],
      "suggestion": "Consolidate into one helper and have the other two call it.",
      "effort": "small"
    },
    {
      "id": "DRY-02",
      "principle": "DRY",
      "detector": "repeated-sequence",
      "severity": "high",
      "confidence": "verified",
      "title": "Session setup repeated across two flows",
      "rationale": "load_user, refresh_token and audit_login run in sequence in both user_login and password_reset.",
      "sites": [
        { "file": "src/auth/session.py", "line": 22, "symbol": "load_user",
          "snippet": "def load_user(request):\n    ..." },
        { "file": "src/auth/session.py", "line": 40, "symbol": "refresh_token",
          "snippet": "def refresh_token(user):\n    ..." }
      ],
      "flows": ["user_login", "password_reset"],
      "suggestion": "Extract the three-call sequence into one begin_session helper.",
      "effort": "medium"
    },
    {
      "id": "KISS-01",
      "principle": "KISS",
      "detector": "complexity-hotspot",
      "severity": "high",
      "confidence": "verified",
      "title": "handle_request has a fan-out of 11",
      "rationale": "handle_request calls 11 functions directly, above the fan-out threshold of 8.",
      "sites": [
        { "file": "src/web/views.py", "line": 63, "symbol": "handle_request",
          "snippet": "def handle_request(req):\n    ..." }
      ],
      "metric": "fan-out",
      "value": 11,
      "suggestion": "Group the validation, persistence and notification calls into three helpers.",
      "effort": "medium"
    },
    {
      "id": "YAGNI-01",
      "principle": "YAGNI",
      "detector": "unreached",
      "severity": "low",
      "confidence": "unverified",
      "title": "legacy_export is not reached by any mapped flow",
      "rationale": "Not reached by any of the 14 mapped flows — confirm before deleting. Tracing cannot see reflection, dependency injection or configuration-declared entry points.",
      "sites": [
        { "file": "src/reports/legacy.py", "line": 7, "symbol": "legacy_export",
          "snippet": "def legacy_export(rows):\n    ..." }
      ],
      "exported": true,
      "suggestion": "Check for dynamic callers and configuration references, then decide.",
      "effort": "small"
    }
  ]
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --group dev pytest tests/test_report_schema.py -v`

Expected: PASS, 8 tests.

Note what the ordering test is checking against this fixture: severities run `high`, `high`, `high`, `low`, and within the three `high` findings the site counts run 3, 2, 1 — descending, as required.

- [ ] **Step 5: Document the command in the README**

Add this section to `README.md`, immediately after the "Whole-codebase mode" section that phase 2 added:

````markdown
### Quality reporting

Once a whole-codebase map exists, analyze it:

```text
/code-flow.quality
/code-flow.quality --read-code
```

This reads `Code_Flows/index.json`, `inventory.json` and every `<flow>.json`, then
writes `Code_Flows/quality-report.json` and `Code_Flows/quality-report.md`. Four
detectors run:

| Detector | Principle | Reports |
|---|---|---|
| duplicate-intent | DRY | The same work implemented in several places |
| repeated-sequence | DRY | Call chains repeated across flows |
| complexity-hotspot | KISS | High fan-out, deep nesting, very long functions |
| unreached | YAGNI | Catalogued functions no mapped flow reaches |

Severity is rule-based — thresholds, not impressions — so findings do not all
drift toward "medium".

`--read-code` opens the files the candidate findings cite and confirms each
against current source, marking findings `verified` or `unverified`. It verifies
candidates rather than re-scanning the repository, so it costs far less than
mapping. It requires the source tree to be present and current, not just the
artifacts.

The report **never edits your code** and never instructs deletion. Unreached
findings are candidates: tracing here is search and reading, so it cannot see
reflection, dependency injection, framework hooks or entry points declared in
configuration. Anything exported is capped at low severity.

Coverage leads every report. If the trace pass mapped 14 of 17 entry points, the
banner says so, and a clean section means clean *within what was mapped* — not a
clean bill of health.

Two things stop the command rather than degrading it: no `inventory.json` (run
`/code-flow.map --whole-code-base` first), and an `index.json` or `inventory.json`
that does not parse. A single unreadable `<flow>.json` does not stop it — that
flow is skipped and counted in the banner.

On a `--detail thin` map, duplicate-intent is skipped unless you pass
`--read-code`: a thin map carries no code snippets, so that detector has no
evidence to cite.
````

Also update the artifacts list earlier in the README so `quality-report.json` and `quality-report.md` appear alongside the existing files.

- [ ] **Step 6: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all pass. Python gains 8 tests from `test_report_schema.py`. Node unchanged at 10.

- [ ] **Step 7: Re-run the parity script**

Run the script from Task 1 Step 8 unchanged. Expected: `0` and `OK`.

This task edits no template, so the result must be identical to Task 5's. If it is not, something outside this task changed a template.

- [ ] **Step 8: Final end-to-end host parity read**

Read all three quality templates end-to-end, one after another, and derive that every rule from Tasks 1-5 is present in each: argument parsing and the no-source-writes rule; all three artifact kinds, both stop conditions, the do-not-overwrite rule, the skip-one-flow rule and the thin-map skip; all four detectors with all seven thresholds, the exact-id join, the three-way role split, the exported cap, candidate-never-verdict, and one-cluster-one-finding; verify-only-cited-files, both confidence values, line correction, verify-before-drop, and staleness-never-stops; both output paths in the right order, every report and banner field, coverage-leads, deterministic ordering, the no-findings rule, and "catalogued" rather than "all".

This read is what phase 1 skipped four times. Do it against the files, not against this plan.

- [ ] **Step 9: Commit**

```bash
git add examples/sample-report.json tests/test_report_schema.py README.md
git commit -m "feat: ship the report fixture, make its schema executable, document the command"
```

---

## What this phase does not verify

No automated check catches a rule that is *present but wrong* in a template. The contract tests assert that field names, thresholds and key phrases appear in the right region — not that the surrounding rule is correct, and not that an assistant following it produces a good report. The detectors run inside an AI assistant and cannot be unit tested conventionally.

That class of defect is caught by the end-to-end host parity read at the close of each task, and by review. This is the same limitation phases 1 and 2 disclosed; it has not changed, and shipping a fourth detector does not change it either.

Two things this phase deliberately leaves undone, both phase 3b:

- `templates/shared/report.template.html` and the `quality-report.html` output. The JSON this phase writes is what that viewer will consume, which is why it is written first and separately.
- Viewer-validation tests — substituting malformed JSON and asserting the error card path triggers rather than a blank page. That machinery does not exist today for `viewer.template.html` either, which has only a token-count contract test. Phase 3b builds it and should retrofit it to the flow viewer while it is there.
