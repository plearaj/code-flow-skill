# Code Flow 1.1.0 — Phase 2 Whole-Codebase Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--whole-code-base` and `--detail` to `code-flow.map`, so the command can catalogue an entire repository into `inventory.json` and trace its entry points across resumable sessions — producing the two-pass artifact set that phase 3's quality report consumes.

**Architecture:** This repository is an *installer*, not an analyzer. Both CLIs (`bin/install.js`, `src/code_flow_skill/cli.py`) only copy prompt-template files into a consuming project; all analysis behavior lives in the prompt text of the templates. **Phase 2 therefore touches no installer code and adds no CLI flag** — `--whole-code-base` and `--detail` are parsed by the AI assistant out of the user's argument string, exactly the way the feature name already is. The work is: extend the prompt text of three host templates, and extend the content-contract tests that assert those templates still say what the spec requires.

**Tech Stack:** Node 24 (`node:test`, built in), Python 3.12 + pytest, hatchling, uv. No new dependencies of any kind.

## Global Constraints

- Target version is exactly `1.1.0`, set identically in `package.json` and `pyproject.toml`. Phase 2 is additive within 1.x — it carries no breaking change.
- Root `templates/` is the single source of truth. `src/code_flow_skill/templates/` must not exist.
- Installers are plain file copies. **No installer file is modified in this phase.** If a task seems to require an installer change, stop and report — it means the design was misread.
- `--detail` is one three-valued flag (`thin|standard|verbose`), never separate `--thin`/`--verbose` booleans, which would leave `--thin --verbose` undefined.
- Every path written into a generated artifact uses forward slashes and is repo-relative. `meta.root` is the one absolute path.
- Reports and prompts say **"catalogued"**, never "all". Discovery is Glob/Grep/Read, not an AST walk, so the catalog is best-effort and must never claim completeness.
- `coverage` always records what was actually done, never what was intended. A partial pass is not an error; it is recorded and surfaced.
- Windows is the development platform. `npm test` is `node --test "test/**/*.test.js"` — the bare `node --test test/` form fails with MODULE_NOT_FOUND on this machine's Node v24.11.1. Python tests: `uv run --group dev pytest -v`.
- No runtime dependencies in either package. `pytest` stays a dev dependency; Node uses its built-in runner.
- Do not use `git add -A`; stage explicit paths.

### Host parity rule (binding on every task)

Three host templates must stay semantically equivalent:

| Host | File | Shape |
|---|---|---|
| Claude | `templates/claude/code-flow.map.md` | Markdown, `#### N. Title` sections, `$ARGUMENTS` |
| Gemini | `templates/gemini/code-flow.map.toml` | The same prose inside a TOML `prompt = '''…'''` string |
| Copilot | `templates/copilot/code-flow.map.prompt.md` | Markdown with `mode: agent` frontmatter, a numbered list plus trailing sections |

- **Claude's and Gemini's bodies carry the same content from `#### 1.` onward, but are NOT byte-identical**, and must not be made so. Measured at the phase-2 branch point (`e0276c3`), 33 lines diverge, in exactly three deliberate classes:
  1. **Claude-only tool names removed for Gemini** — Claude says "Use `Glob` to find relevant files", "Use `Grep` to find functions", "Add the docstring using the Edit tool"; Gemini says "Search for relevant files by name pattern" and so on. **Reconciling these would name tools the Gemini host does not have.**
  2. **Fence width** — Claude wraps example blocks in four-backtick fences because its own file is markdown containing nested fences; inside Gemini's TOML `'''` string that wrapper is unnecessary, so Gemini uses plain three-backtick fences.
  3. **ASCII substitution** — Claude writes `∈` and `≤`; Gemini writes "is one of" and "up to".

  **Do not "fix" any of these.** An earlier revision of this plan asserted byte-identity; that was wrong about the repository, and Task 1 caught it.

- **The real rule, binding on every task:** every block phase 2 *adds* must be byte-identical between Claude and Gemini — the new text names no host-specific tool and needs no nested fence, so there is no reason for it to differ — and phase 2 must not change the pre-existing 33-line divergence. Both are checked by the parity script in Task 1 Step 7, which every later task re-runs.
- **Copilot says the same thing in its own voice** — its numbered-list register, not Claude's heading register. Same rules, same field names, same derivations.
- **Phase 1 lost four review rounds to this.** Every miss was a rule present in two hosts and absent from the third, and every miss was *outside* the section under review. So: at the end of each task, read all three templates **end-to-end** and **derive** — do not assert — that each rule the task added is present in each host. Record the derivation in the task report.
- This plan gives each new rule **once**, as canonical text. Apply that one block to all three hosts. Do not expect a separate per-host block; asking for one is how phase 1's Copilot template got abridged five times.

## File Structure

**Created:**
- `docs/superpowers/plans/2026-08-07-phase2-whole-codebase.md` — this plan
- `tests/test_node_ids.py` — executable check that the repo's own example artifacts obey the `id` derivation rule

**Modified:**
- `templates/claude/code-flow.map.md` — flags in step 1; new `## Whole-Codebase Mode` section after step 7
- `templates/gemini/code-flow.map.toml` — the same, byte-identical from `#### 1.` onward
- `templates/copilot/code-flow.map.prompt.md` — the same rules in its own register
- `tests/test_template_contracts.py` — generalized region helper; new contract tests for flags, inventory, and coverage
- `examples/sample-flow.json` — node ids brought into line with the derivation rule
- `docs/superpowers/specs/2026-08-06-dry-kiss-yagni-reporting-design.md` — fix the `index.json` example that its own prose rule cannot produce
- `README.md` — whole-codebase mode, the two flags, the new artifacts
- `package.json`, `pyproject.toml` — version 1.1.0

**Not modified, deliberately:** `bin/install.js`, `src/code_flow_skill/cli.py`, `templates/shared/viewer.template.html`. Phase 2 changes what the assistant is told to produce, not what the installer copies or how the viewer renders.

**A note on file size.** Claude's template is 184 lines and will end near 300. That is large for a prompt, but a slash command is one file — it cannot be split without changing what gets installed. Keep the additions tight: rules, not prose. If a section you are adding runs past ~40 lines, that is a signal to cut words, not to split the file.

---

### Task 1: Close the phase-1 residuals and make the `id` rule executable

Phase 1 shipped with three known gaps, all in the `id` contract that phase 2's inventory is about to depend on. The inventory's whole purpose is that a flow node and an inventory entry for the same function carry the same `id` — so the rule must be unambiguous *before* a second producer starts emitting ids.

**Files:**
- Modify: `templates/claude/code-flow.map.md:106`
- Modify: `templates/gemini/code-flow.map.toml:96`
- Modify: `templates/copilot/code-flow.map.prompt.md:49`
- Modify: `examples/sample-flow.json`
- Modify: `docs/superpowers/specs/2026-08-06-dry-kiss-yagni-reporting-design.md:161-162`
- Create: `tests/test_node_ids.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `tests/test_node_ids.py` exposes `derive_id(file: str, name: str) -> str` — the executable form of the derivation rule, used only inside that module. It takes a repo-relative path with forward slashes and an unqualified function name and returns the normalized id string. It does **not** implement the same-name collision suffix, which depends on the file's contents — see Step 4. No later task imports it; its value is that the rule stops being unverifiable prose.

- [ ] **Step 1: Write the failing test**

Create `tests/test_node_ids.py`:

```python
"""The node `id` derivation rule, made executable.

`id` is prose in three prompt templates, which means nothing checks that the
rule is followed — including by this repository's own example artifacts. This
module implements the rule once and asserts the examples obey it, so a change
to the rule that the examples contradict fails the suite instead of shipping.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def derive_id(file: str, name: str) -> str:
    """Return the `id` for a function named ``name`` defined in ``file``.

    Mirrors the rule stated in every map template: drop the extension from the
    path's last segment only, append the unqualified function name, lowercase,
    replace every character outside ``[a-z0-9_]`` with ``_``, collapse runs, and
    trim. The same-name-in-one-file collision suffix (``_l<line>``) is not
    applied here — it depends on the *file's* contents, which a pure path/name
    function cannot see.
    """
    head, _, last = file.rpartition("/")
    stem = last.rpartition(".")[0] or last
    combined = f"{head}/{stem}_{name}" if head else f"{stem}_{name}"
    slug = re.sub(r"[^a-z0-9_]+", "_", combined.lower())
    return slug.strip("_")


def test_derive_id_matches_the_documented_example() -> None:
    assert derive_id("src/web/views.py", "login_view") == "src_web_views_login_view"


def test_derive_id_drops_the_extension_from_the_last_segment_only() -> None:
    assert derive_id("src/v2.1/handler.py", "run") == "src_v2_1_handler_run"


def test_derive_id_keeps_a_dotless_filename_whole() -> None:
    assert derive_id("bin/entrypoint", "main") == "bin_entrypoint_main"


def test_sample_flow_node_ids_follow_the_rule(repo_root: Path) -> None:
    """The shipped example must obey the rule the templates state.

    `label` is the display form (`login_view()`); the function name is that with
    the trailing parens stripped.
    """
    flow = json.loads((repo_root / "examples" / "sample-flow.json").read_text(encoding="utf-8"))
    wrong = []
    for node in flow["nodes"]:
        name = node["label"].removesuffix("()")
        expected = derive_id(node["file"], name)
        if node["id"] != expected:
            wrong.append(f"{node['id']} should be {expected}")
    assert not wrong, "sample-flow.json node ids do not follow the derivation rule: " + "; ".join(wrong)


def test_sample_flow_edges_resolve_to_nodes(repo_root: Path) -> None:
    """Every edge endpoint must name a node that exists.

    The templates state this as a hard rule and the viewer enforces it at load
    time with an error card. Renaming node ids without renaming both endpoints
    of every edge is the exact way to break it.
    """
    flow = json.loads((repo_root / "examples" / "sample-flow.json").read_text(encoding="utf-8"))
    ids = {node["id"] for node in flow["nodes"]}
    dangling = [
        f"{edge['from']} -> {edge['to']}"
        for edge in flow["edges"]
        if edge["from"] not in ids or edge["to"] not in ids
    ]
    assert not dangling, "edges reference missing nodes: " + "; ".join(dangling)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_node_ids.py -v`

Expected: the three `derive_id` unit tests PASS (they test the helper you just wrote), and `test_sample_flow_node_ids_follow_the_rule` FAILS, listing bare ids like `login_view should be src_web_views_login_view`. `test_sample_flow_edges_resolve_to_nodes` passes at this point — the example is internally consistent, just not conformant.

If `test_sample_flow_node_ids_follow_the_rule` passes, stop and report: it means the example was already fixed, or `label`/`file` are shaped differently than assumed, and the rest of this task needs rechecking against reality.

- [ ] **Step 3: Fix `examples/sample-flow.json`**

Rewrite every `nodes[].id` to the value `derive_id` produces, and rewrite every `edges[].from` and `edges[].to` to match. Change nothing else — not labels, not descriptions, not snippets, not the `meta` block.

Work from the test output: it names each wrong id and its expected replacement. Do the node ids first, then sweep the edges; `test_sample_flow_edges_resolve_to_nodes` is what catches a missed endpoint.

- [ ] **Step 4: Add the decorator/definition-line clarification to all three hosts**

The collision suffix says "append `_l` and the line the function is defined on". Nothing says whether that is the `def` line or a decorator line above it. While `line` was display-only an off-by-one was cosmetic; now it is identity-critical.

In each of the three templates, find the sentence beginning "If **the file itself** defines more than one function with that name" and replace the clause "append `_l` and the line the function is defined on" with:

```
append `_l` and the line number of the function's own definition keyword — the
`def`, `function`, `func` or `fn` line itself, never a decorator, annotation or
comment line above it
```

Claude and Gemini take this text verbatim and stay byte-identical. Copilot's step 5 carries the same rule inline; make the same replacement there, keeping its sentence flow.

- [ ] **Step 5: Fix the spec's contradictory example**

`docs/superpowers/specs/2026-08-06-dry-kiss-yagni-reporting-design.md:161-162` shows an `index.json` flow entry whose `entry` is a bare function name:

```json
    { "slug": "user_login", "title": "User Login", "file": "user_login.json",
      "entry": "login_view", "nodes": 9 }
```

The spec's own prose at line 195 says `id` is derived from `file` + `name`, so `login_view` is not a producible id and the example contradicts the rule. Replace `"entry": "login_view"` with `"entry": "src_web_views_login_view"`, matching the `inventory.json` example above it, which already follows the prose.

Change only that one value. The spec is an approved design document; this is a correction of a self-contradiction, not a redesign.

- [ ] **Step 6: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: all Python tests pass including the five new ones; Node unchanged at 7 passing. Output pristine — no warnings, no skips.

- [ ] **Step 7: Derive host parity**

Read all three templates end-to-end. For the `id` rule specifically, confirm in each host: extension dropped from the last segment only; unqualified name; lowercase-and-normalize; the collision suffix with the new definition-keyword clarification.

Then run the Claude/Gemini parity script. It does **not** check byte-identity — see the Host parity rule above; the two bodies legitimately differ in 33 lines. It checks that phase 2 did not *add* divergence:

```bash
python - <<'PY'
import tomllib, pathlib, difflib
claude = pathlib.Path("templates/claude/code-flow.map.md").read_text(encoding="utf-8")
gemini = tomllib.loads(pathlib.Path("templates/gemini/code-flow.map.toml").read_text(encoding="utf-8"))["prompt"]
c = claude[claude.index("#### 1."):].splitlines()
g = gemini[gemini.index("#### 1."):].splitlines()
diff = [l for l in difflib.unified_diff(c, g, lineterm="", n=0)
        if l[:1] in "+-" and l[:3] not in ("+++", "---")]
print(f"divergent lines: {len(diff)} (baseline 33)")
print("OK" if len(diff) == 33 else "DIVERGENCE CHANGED")
for l in diff:
    print(l)
PY
```

Expected: `divergent lines: 33` and `OK`.

- **More than 33** means your edit landed differently in the two hosts. Find it in the printed lines and close it.
- **Fewer than 33** means you "fixed" one of the three deliberate adaptations. Restore it — the Gemini prompt must not name Claude-only tools.
- Every printed line must belong to one of the three classes named in the Host parity rule. A divergent line that is none of them is a real defect regardless of the count.

- [ ] **Step 8: Commit**

```bash
git add tests/test_node_ids.py examples/sample-flow.json templates/claude/code-flow.map.md templates/gemini/code-flow.map.toml templates/copilot/code-flow.map.prompt.md docs/superpowers/specs/2026-08-06-dry-kiss-yagni-reporting-design.md
git commit -m "fix: make the node id rule executable and bring the example into line"
```

---

### Task 2: Parse `--whole-code-base` and `--detail`

The flags are read by the assistant out of the argument string. Nothing in either installer changes. This task adds the parsing rules and the mode dispatch; the mode's *body* arrives in Tasks 3 and 4.

**Files:**
- Modify: `templates/claude/code-flow.map.md` (step 1)
- Modify: `templates/gemini/code-flow.map.toml` (step 1)
- Modify: `templates/copilot/code-flow.map.prompt.md` (item 1)
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: nothing from Task 1 except that its parity check is now routine.
- Produces: the section anchor `## Whole-Codebase Mode` (Claude/Gemini) and `## Whole-codebase mode` (Copilot), which Tasks 3 and 4 fill in and which the region helper below keys on. Also produces `_section_region(text, start, end)` in `tests/test_template_contracts.py`, signature `(text: str, start: re.Pattern[str], end: re.Pattern[str]) -> str`, returning the slice from the first `start` match to the next `end` match (or end of text).

- [ ] **Step 1: Write the failing contract tests**

Add to `tests/test_template_contracts.py`, after the existing `INDEX_FIELD_NAMES` block:

```python
# --- Phase 2: whole-codebase mode -----------------------------------------

# Anchored on the *heading*, not the words. Every host also mentions
# "Whole-Codebase Mode" inline in step 1, where it tells the reader to jump to
# the section — and that reference comes first in the file. A loose pattern
# would start the region at that cross-reference, swallowing all of feature
# mode and making every assertion scoped to this region vacuous.
_MODE_SECTION_START = re.compile(r"^#{2,3} +Whole-[Cc]odebase +[Mm]ode *$", re.MULTILINE)


def _section_region(text: str, start: re.Pattern[str], end: re.Pattern[str]) -> str:
    """Return the slice of ``text`` from the first ``start`` match to the next
    ``end`` match (or to the end of the text if ``end`` never matches).

    Region scoping is what keeps these content assertions from being vacuous:
    a bare substring search over a whole template passes on incidental prose
    elsewhere in the file, so deleting the rule under test would not fail.
    """
    start_match = start.search(text)
    assert start_match, f"template has no section matching {start.pattern!r}"
    begin = start_match.start()
    end_match = end.search(text, begin)
    return text[begin : end_match.start() if end_match else len(text)]


# `thin`, `standard` and `verbose` are searched for as the single token
# `thin|standard|verbose`, the form every host writes them in. Searched
# separately they would be vacuous: "standard" and "thin" already occur inside
# ordinary words and prose elsewhere in these templates.
WHOLE_CODEBASE_FLAGS = ("--whole-code-base", "--detail", "thin|standard|verbose")


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_documents_the_mode_flags(repo_root: Path, host: str, name: str) -> None:
    """Every host must document both option flags and all three detail levels.

    These are the user-facing surface of phase 2. A host that omits `--detail`
    silently gives its users a different command from the other two.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    for flag in WHOLE_CODEBASE_FLAGS:
        assert flag in text, f"{host}/{name} never mentions {flag}"


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_has_a_whole_codebase_section(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert _MODE_SECTION_START.search(text), f"{host}/{name} has no whole-codebase mode section"
```

Then refactor the existing `_index_instructions_region` to delegate, so there is one region implementation rather than two:

```python
def _index_instructions_region(text: str) -> str:
    """Return only the slice of a map template that gives the Step 6
    index/sidecar instructions.

    `slug`, `entry`, and `nodes` are not unique to Step 6 — they also show
    up incidentally elsewhere in every template (the flow-data JSON's own
    `nodes` array, the node `kind` enum's `entry` value, `meta.slug` in the
    step 5a example). A bare substring search over the whole template would
    pass even if the Step 6 bullets describing the index entry were deleted
    entirely, because those other occurrences would still be there. Scoping
    to the region between the machine-readable-artifacts heading and the
    next section closes that hole.
    """
    return _section_region(text, _INDEX_SECTION_START, _INDEX_SECTION_END)
```

Move `_section_region` above `_index_instructions_region` so the delegation resolves.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`

Expected: `test_map_template_documents_the_mode_flags` and `test_map_template_has_a_whole_codebase_section` FAIL for all three hosts (6 failures), with messages naming `--whole-code-base` and the missing section. The pre-existing tests still pass — if any of them broke, the `_section_region` refactor changed behavior and must be corrected before continuing.

- [ ] **Step 3: Add flag parsing to Claude and Gemini**

In both templates, replace the body of `#### 1. Identify the Target Flow` — from the paragraph beginning "The user's input" through the paragraph ending "`password_reset.md`)" — with:

```markdown
The user's input (`$ARGUMENTS`) says what to document. Read it first for two option
flags. They are options, not part of the feature name — strip them out before you
derive any filename from what is left.

- `--whole-code-base` — map the whole repository instead of one feature. If it is
  present, skip the rest of this section and everything through step 7, and follow
  **Whole-Codebase Mode** at the end of this document instead.
- `--detail thin|standard|verbose` — how much evidence each catalogued function
  carries. Default `standard`. It only changes anything in whole-codebase mode; if
  it appears without `--whole-code-base`, accept it silently rather than erroring.
  If it appears with a value that is not one of those three, tell the user what you
  read, use `standard`, and carry on.

Everything from here through step 7 is **feature mode**, the default.

The remaining input describes the functionality to document. If it is empty,
analyze the project structure and suggest 3-5 key flows, then ask the user to pick
one.

Use the functionality name to derive the output filename. Convert to snake_case
(e.g., "user login" → `user_login.md`, "password reset" → `password_reset.md`).
```

- [ ] **Step 4: Add the section anchor to Claude and Gemini**

Append to the end of both templates (in Gemini, before the closing `'''`):

```markdown

## Whole-Codebase Mode

Reached only when the user passed `--whole-code-base`. Two passes: catalogue what
exists, then trace how it runs. The passes are separate because they answer
different questions and because the second one is far more expensive than the first.

**This mode never edits source files.** Feature mode adds docstrings as it goes
(step 3); at repository scale that would be a sweeping unrequested rewrite, so here
you only read. Report undocumented functions in the inventory's `purpose` field
instead — inferred from the body when there is no docstring.
```

The two passes are added in Tasks 3 and 4 under this heading.

- [ ] **Step 5: Add the same to Copilot**

In `templates/copilot/code-flow.map.prompt.md`, replace numbered item 1 with:

```markdown
1. **Read the request for option flags first.** `--whole-code-base` maps the whole repository instead of one feature — if it is there, ignore steps 2-7 and follow "Whole-codebase mode" at the end of this prompt. `--detail thin|standard|verbose` sets how much evidence each catalogued function carries, default `standard`; it only matters in whole-codebase mode, so accept it silently otherwise, and if its value is not one of those three, say what you read, use `standard`, and carry on. Flags are options, not part of the feature name — strip them out. Then **identify the target flow** from what is left and derive a snake_case filename (e.g. "user login" → `user_login.md`). If no functionality was named, analyze the project structure, suggest 3-5 key flows, and ask the user to pick one before going any further. Steps 2-7 are feature mode, the default.
```

And append at the end of the file:

```markdown

## Whole-codebase mode

Reached only when the user passed `--whole-code-base`. Two passes: catalogue what exists, then trace how it runs. They are separate because they answer different questions and because the second is far more expensive than the first.

**This mode never edits source files.** Step 3 adds docstrings in feature mode; at repository scale that would be a sweeping unrequested rewrite, so here you only read. Record what a function does in the inventory's `purpose` field instead — inferred from the body when there is no docstring.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`

Expected: PASS, including the 6 previously failing cases.

- [ ] **Step 7: Run the full suite and check the TOML still parses**

Run: `uv run --group dev pytest -v && npm test`

Then:

```bash
python -c "import tomllib,pathlib;d=tomllib.loads(pathlib.Path('templates/gemini/code-flow.map.toml').read_text(encoding='utf-8'));print(sorted(d),len(d['prompt']))"
```

Expected: both suites pass pristine; the TOML prints `['description', 'prompt']` and a length. A `TOMLDecodeError` means the appended text broke the `'''` string — most likely because it contains `'''`.

- [ ] **Step 8: Derive host parity**

Read all three templates end-to-end. Confirm in each: both flags named, the default `standard` stated, the invalid-value behavior stated, the "strip flags before deriving the filename" rule, the mode dispatch, and the never-edit-source rule.

Run the parity script from Task 1 Step 7. Expected: `divergent lines: 33` and `OK`. **Note that this task rewrites step 1's body in both hosts** — the block given in Step 3 replaces Claude's wording *and* Gemini's, so the three step-1 lines that diverge in the baseline are replaced by identical text in both. That lowers the count. If the script prints fewer than 33, recount by hand: the acceptable new baseline is 33 minus exactly the step-1 lines your replacement subsumed, and every remaining divergent line must still belong to one of the three deliberate classes. Record the new baseline in your report and in the Host parity rule at the top of this plan, so Tasks 3-5 check against the right number.

- [ ] **Step 9: Commit**

```bash
git add templates/claude/code-flow.map.md templates/gemini/code-flow.map.toml templates/copilot/code-flow.map.prompt.md tests/test_template_contracts.py
git commit -m "feat: parse --whole-code-base and --detail, dispatch to whole-codebase mode"
```

---

### Task 3: Pass 1 — the inventory and the file census

The breadth pass. It traces nothing: it walks the repository, catalogues every function into `inventory.json`, and records the file census plus breadth coverage into `index.json`.

**Files:**
- Modify: `templates/claude/code-flow.map.md` (Whole-Codebase Mode section)
- Modify: `templates/gemini/code-flow.map.toml` (same)
- Modify: `templates/copilot/code-flow.map.prompt.md` (same)
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: `_section_region(text, start, end)` and `_MODE_SECTION_START` from Task 2; `_field_reference(field)` from phase 1 (already in the file — matches a delimited field reference, not a bare word).
- Produces: the `inventory.json` contract that Task 4's trace pass and all of phase 3 read. Also produces the constant `INVENTORY_FIELD_NAMES` and the region anchor `_PASS2_START` used by Task 4's tests.

- [ ] **Step 1: Write the failing contract tests**

Add to `tests/test_template_contracts.py`:

```python
INVENTORY_FIELD_NAMES = (
    "id",
    "name",
    "file",
    "line",
    "loc",
    "signature",
    "purpose",
    "role",
    "exported",
    "snippet",
)

# The trace pass heading, used as the end boundary of the inventory region so
# pass 1's assertions cannot be satisfied by text that belongs to pass 2.
# Heading-anchored for the same reason as the mode heading: pass 1's own prose
# says "belong to pass 2", and a loose pattern would end the inventory region
# at that sentence instead of at the section it names.
_PASS2_START = re.compile(r"^#{3,4} +Pass 2\b", re.MULTILINE)


def _inventory_region(text: str) -> str:
    return _section_region(text, _MODE_SECTION_START, _PASS2_START)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_names_inventory_fields(repo_root: Path, host: str, name: str) -> None:
    """Pass 1's instructions must name every field an inventory entry carries.

    Scoped to the region between the whole-codebase heading and the Pass 2
    heading: `file`, `line` and `name` all occur throughout the feature-mode
    half of every template, so an unscoped search would pass even with the
    inventory instructions deleted outright.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _inventory_region(text)
    for field in INVENTORY_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host}/{name} pass 1 instructions are missing the '{field}' field name"
        )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_inventory_file(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "inventory.json" in _inventory_region(text)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_catalogues_tests_rather_than_skipping_them(
    repo_root: Path, host: str, name: str
) -> None:
    """Test files must be catalogued with role "test", never excluded.

    Excluding them makes every test-only helper look unreachable, which
    produces a large class of false dead-code findings in phase 3. This is the
    single rule whose omission would quietly poison the next phase, so it gets
    its own assertion rather than riding on the `role` field-name check.
    """
    region = _inventory_region(
        (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    )
    assert '"test"' in region or "`test`" in region, (
        f"{host}/{name} pass 1 never assigns the test role"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`

Expected: the three new tests FAIL for all three hosts (9 failures). The `_inventory_region` assertion inside `_section_region` will not trip — Task 2 created the heading — so the failures are about missing field names and `inventory.json`, which is the correct reason.

- [ ] **Step 3: Write pass 1 into Claude and Gemini**

Append this to the `## Whole-Codebase Mode` section in both templates, immediately after the never-edit-source paragraph:

````markdown
### Pass 1 — Breadth: catalogue what exists

This pass traces nothing. It records what is there.

**1.1 Choose the files to scan.** Walk the repository from the project root,
honoring `.gitignore`. Skip in addition: `node_modules`, `.venv`, `venv`, `dist`,
`build`, `target`, `vendor`, `third_party`; lockfiles (`package-lock.json`,
`yarn.lock`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `go.sum`); minified or
generated assets (`*.min.js`, `*.min.css`, `*.map`); and anything binary. Count
every skip and attribute it to one reason: `vendored`, `generated`, `binary`, or
`unparsed` for a file you opened but could not read structure from.

**1.2 Catalogue the functions.** Write `Code_Flows/inventory.json` with one entry
per function or method you find:

```json
{
  "schema": 1,
  "functions": [
    {
      "id": "src_auth_validators_validate_email",
      "name": "validate_email",
      "file": "src/auth/validators.py",
      "line": 12,
      "loc": 14,
      "signature": "validate_email(value: str) -> bool",
      "purpose": "Return True if value looks like an email address.",
      "role": "source",
      "exported": false,
      "snippet": "def validate_email(value):\n    ..."
    }
  ]
}
```

- `id` — derived exactly as in step 5a, from the same `file` and unqualified
  `name`. This is the whole point of the pass: a flow node and the inventory entry
  for the same function carry the same `id`, and that join is what lets a later
  command compute which catalogued functions no flow ever reaches.
- `line` — the line of the function's own definition keyword, never a decorator or
  comment above it. `loc` — its length in lines, definition line through last line
  inclusive.
- `signature` — the declaration as written, on one line, without the body.
- `purpose` — one sentence. Use the docstring if there is one; otherwise infer it
  from the body. Do not edit the source file to add one.
- `role` — `"test"` if the file is a test (a `test_*`/`*_test`/`*.test.*`/`*.spec.*`
  name, or a `tests/`, `test/`, `spec/`, `__tests__/` directory), `"source"`
  otherwise. **Catalogue tests, never skip them.** Excluding them would make every
  helper that only tests use look unreachable.
- `exported` — whether the function is public API. A per-language heuristic, not a
  proof: the `export` keyword in JS/TS, a name without a leading underscore (and
  `__all__` membership where a module defines it) in Python, an initial capital in
  Go. **When the language or the convention is unclear, use `true`** — wrongly
  calling something private produces a false dead-code claim later, which is the
  more expensive mistake.
- `snippet` — governed by `--detail`:

| `--detail` | `snippet` |
|---|---|
| `thin` | omit it entirely |
| `standard` (default) | include, capped at ~20 lines; omit for functions of 3 lines or fewer, since a trivial accessor tells a duplicate-detector nothing |
| `verbose` | include the full body, uncapped |

  Inside every `snippet`, replace each `</` with `<\/`, exactly as in step 5a.

**1.3 Record the file census.** In `Code_Flows/index.json`, set `meta.mode` to
`"whole-code-base"` and `meta.detail` to the level you used, then record one entry
per scanned file and the breadth half of `coverage`:

```json
{
  "meta": { "root": "<absolute project root, forward slashes>",
            "generated": "<today, YYYY-MM-DD>", "mode": "whole-code-base",
            "detail": "standard", "schema": 1 },
  "coverage": { "filesScanned": 214, "filesSkipped": 12,
                "skipReason": { "vendored": 9, "unparsed": 3 },
                "functionsCatalogued": 1180 },
  "files": [
    { "path": "src/auth/validators.py", "size": 4210, "hash": "sha256:9f2a1c" }
  ],
  "flows": []
}
```

The `flows` array and the rest of `coverage` belong to pass 2 — preserve whatever
is already there, and preserve every `coverage` value you did not compute. The
same rule as feature mode applies: if `index.json` exists but does not parse,
**stop**, report it, and do not overwrite it.

`hash` lets a later command warn that the map is stale without re-reading source.
Compute it with whatever the environment provides — `sha256sum <file>`,
`Get-FileHash -Algorithm SHA256 <file>`, or `certutil -hashfile <file> SHA256` —
and record `sha256:` followed by the first 6 hex characters. **If you cannot run
commands here, set `"hash": null` for every file and say so in your final report.
Never invent a hash value**; `size` alone still catches most edits.

**1.4 Resuming.** If `files` already lists a path whose `size` and `hash` are
unchanged, keep that file's existing `functions` entries and move on rather than
re-reading it. A repository too large to catalogue in one session is finished by
running the command again.
````

- [ ] **Step 4: Write pass 1 into Copilot**

Take the block you just wrote in Step 3 of this task and append it to Copilot's `## Whole-codebase mode` section in its own register. Use `### Pass 1 — breadth: catalogue what exists` as the heading.

The register difference is heading style and how the reader is addressed — not content. **Every rule, field name, table row and JSON key from Step 3 must appear.** Keep the two JSON blocks and the `--detail` table verbatim: they are data, not voice.

You are not given a separate Copilot block on purpose. Phase 1 supplied per-host blocks and the Copilot one came in abridged five times running; a single canonical block applied three times is the fix.

After writing it, walk the Step 3 block rule by rule against what you wrote and list any rule present in one and not the other. That list must be empty before you continue.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`

Expected: PASS, including the 9 previously failing cases.

- [ ] **Step 6: Prove the region scoping has teeth**

The inventory assertions are only worth anything if they fail when the inventory instructions go missing. Verify that:

```bash
python - <<'PY'
import pathlib, re
p = pathlib.Path("templates/claude/code-flow.map.md")
original = p.read_text(encoding="utf-8")
start = original.index("### Pass 1")
end = original.index("### Pass 2") if "### Pass 2" in original else len(original)
p.write_text(original[:start] + original[end:], encoding="utf-8")
PY
uv run --group dev pytest tests/test_template_contracts.py -k inventory -v
```

Expected: FAIL for the claude cases. Then restore:

```bash
git checkout templates/claude/code-flow.map.md
```

Confirm `git status` is clean before moving on. Record the red output in your report — a scoping test that cannot go red is decoration.

- [ ] **Step 7: Run the full suite and check the TOML**

Run: `uv run --group dev pytest -v && npm test`, then the `tomllib` parse check from Task 2 Step 7.

Expected: both suites pass pristine; the TOML parses.

- [ ] **Step 8: Derive host parity**

Read all three templates end-to-end. Confirm in each: the exclude list, the four skip reasons, all ten inventory fields with their rules, the id-join rationale, the test-role rule, the `exported` default-to-true rule, all three `--detail` rows, the snippet escaping rule, `meta.detail`, the breadth coverage fields, the `files[]` shape, the hash fallback, and the resume rule.

Run the parity script from Task 1 Step 7 and confirm the count matches the baseline Task 2 recorded in the Host parity rule, with `OK` or a hand-verified equivalent. Pass 1's block is added verbatim to both hosts, so it must contribute **zero** new divergent lines. Note the fence-width adaptation: the plan quotes this block inside a four-backtick fence, but that wrapper is the plan's quoting device — what you write into each template starts at `### Pass 1`, with plain three-backtick fences around the two JSON examples in both hosts.

- [ ] **Step 9: Commit**

```bash
git add templates/claude/code-flow.map.md templates/gemini/code-flow.map.toml templates/copilot/code-flow.map.prompt.md tests/test_template_contracts.py
git commit -m "feat: pass 1 — catalogue functions into inventory.json and record the file census"
```

---

### Task 4: Pass 2 — entry-point discovery, tracing, and idempotent re-runs

The expensive pass. It finds the repository's entry points, traces each one with the existing per-flow procedure, and can be stopped and resumed without redoing work.

**Files:**
- Modify: `templates/claude/code-flow.map.md` (Whole-Codebase Mode section)
- Modify: `templates/gemini/code-flow.map.toml` (same)
- Modify: `templates/copilot/code-flow.map.prompt.md` (same)
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: `_section_region`, `_MODE_SECTION_START`, `_PASS2_START` and `_field_reference` from Tasks 2 and 3.
- Produces: the complete `coverage` block that phase 3 reads to decide how much of the map it can trust.

- [ ] **Step 1: Write the failing contract tests**

Add to `tests/test_template_contracts.py`:

```python
COVERAGE_FIELD_NAMES = (
    "filesScanned",
    "filesSkipped",
    "skipReason",
    "functionsCatalogued",
    "entryPointsFound",
    "flowsTraced",
)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_names_every_coverage_field(repo_root: Path, host: str, name: str) -> None:
    """Whole-codebase mode must account for all six coverage fields.

    Phase 3 decides how much of the map it can trust from these numbers, and
    `flowsTraced` below `entryPointsFound` is how a partial run stays visible
    rather than passing for a complete one.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _section_region(text, _MODE_SECTION_START, re.compile(r"\Z"))
    for field in COVERAGE_FIELD_NAMES:
        assert _field_reference(field).search(region), (
            f"{host}/{name} whole-codebase mode never mentions '{field}'"
        )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_skips_already_registered_flows(
    repo_root: Path, host: str, name: str
) -> None:
    """Re-running must skip flows already in index.json.

    Without this, a repository too large for one session can never finish: each
    run redoes the flows the previous run completed.

    Keyed on the literal clause "do not re-trace" rather than on the words
    "already" and "skip", both of which occur elsewhere in the same region
    ("every entry point not already mapped", "skip step 3") and would leave
    this assertion green with the resume rule deleted. The cost of keying on a
    phrase is that rewording the rule breaks the test; the failure message
    below says exactly which phrase is expected, and all three hosts are
    required to carry it verbatim.
    """
    region = _section_region(
        (repo_root / "templates" / host / name).read_text(encoding="utf-8"),
        _PASS2_START,
        re.compile(r"\Z"),
    )
    assert "do not re-trace" in region.lower(), (
        f"{host}/{name} pass 2 is missing the resume rule: its instructions for "
        f"an already-registered flow must say 'do not re-trace'"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`

Expected: `test_map_template_names_every_coverage_field` FAILS for all three hosts, naming `entryPointsFound` — Task 3 supplied the first four coverage fields, and the loop stops at the fifth. (`flowsTraced`, the sixth, is also still missing at this point; you will see it only after `entryPointsFound` lands.) `test_map_template_skips_already_registered_flows` FAILS inside `_section_region` with "template has no section matching" and the `Pass 2` heading pattern. Six failures. That second message is the correct one — the section genuinely does not exist yet.

- [ ] **Step 3: Write pass 2 into Claude and Gemini**

Append to the `## Whole-Codebase Mode` section in both templates, after pass 1:

````markdown
### Pass 2 — Trace: map the flows

**2.1 Find the entry points.** An entry point is where execution enters the system
from outside it: HTTP routes and their handlers, CLI commands and subcommands,
`main()`, event and queue handlers, scheduled jobs, and the exported public API.
Use the inventory you just built — `exported` is a strong hint — plus the framework
conventions the repository actually uses (route decorators, a router table, an
`argv` parser, a job registry).

Record how many you found as `coverage.entryPointsFound` **before you trace any of
them**. Recording it first is what makes an unfinished run visible: `flowsTraced`
below `entryPointsFound` means the map is partial.

**2.2 Trace each one.** For every entry point not already mapped, run feature mode's
steps 2, 4, 5 and 6 exactly as written, treating that entry point as the requested
flow — but **skip step 3**: this mode does not edit source. Each flow produces its
own `Code_Flows/<slug>.md`, `.html` and `.json`, and its own entry in `index.json`'s
`flows` array. Derive the slug from the entry point's own name.

**2.3 Skip what is already mapped.** Before tracing, check `index.json`'s `flows`
for that slug. If it is already there, skip it and move on — do not re-trace and do
not overwrite its files. This is what lets a repository be mapped across several
sessions: run the command again and it picks up where it stopped.

**2.4 Stop honestly.** A partial pass 2 is not an error. If you run out of room,
stop cleanly after finishing the flow you are on, leave `index.json` consistent, and
tell the user how many of the entry points you traced and that re-running continues
from there. Set `coverage.flowsTraced` to the length of `flows` — what you actually
did, never what you intended.

**2.5 Report.** Tell the user: the counts from `coverage`, where the artifacts are,
and — if `flowsTraced` is below `entryPointsFound` — that the map is partial and how
to finish it. Say **catalogued**, never "all": this discovery is search and reading,
not a compiler's view of the code, so it is best-effort by construction.
````

- [ ] **Step 4: Write pass 2 into Copilot**

Take the block you just wrote in Step 3 of this task and append it to Copilot's `## Whole-codebase mode` section in its own register, heading `### Pass 2 — trace: map the flows`. Every rule must appear: the entry-point kinds, recording `entryPointsFound` before tracing, reusing steps 2/4/5/6 while skipping step 3, the skip-already-registered rule, the partial-run behavior, and the "catalogued not all" wording.

Two specifics:

- The clause **"do not re-trace"** must appear verbatim. A contract test keys on it, because the looser words around it ("already", "skip") also occur in 2.2 and would leave that test green with the resume rule deleted.
- Copilot's numbered steps are 1-7, not `#### N.` headings — refer to them the way that file already does, so "steps 2, 4, 5 and 6" resolves for a reader who has only that file in front of them.

After writing it, walk the Step 3 block rule by rule against what you wrote and list any rule present in one and not the other. That list must be empty.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`

Expected: PASS, including the 6 previously failing cases.

- [ ] **Step 6: Prove the idempotency assertion has teeth**

```bash
python - <<'PY'
import pathlib
p = pathlib.Path("templates/claude/code-flow.map.md")
original = p.read_text(encoding="utf-8")
start = original.index("**2.3 Skip what is already mapped.**")
end = original.index("**2.4 Stop honestly.**")
p.write_text(original[:start] + original[end:], encoding="utf-8")
PY
uv run --group dev pytest tests/test_template_contracts.py -k already_registered -v
```

Expected: FAIL for the claude case, with the message naming the missing `do not re-trace` clause. Then `git checkout templates/claude/code-flow.map.md` and confirm `git status` is clean. Record the red output in your report.

If it does NOT go red, the clause survives somewhere else in the pass 2 region — find it and say so rather than leaving a decorative test.

- [ ] **Step 7: Run the full suite and check the TOML**

Run: `uv run --group dev pytest -v && npm test`, then the `tomllib` parse check from Task 2 Step 7.

Expected: both suites pass pristine; the TOML parses.

- [ ] **Step 8: Derive host parity**

Read all three templates end-to-end. Confirm in each: the entry-point kinds, `entryPointsFound` recorded before tracing, the step reuse with step 3 skipped, the skip-already-mapped rule, partial-run honesty, `flowsTraced` as what was done, and the "catalogued" wording.

Run the parity script from Task 1 Step 7 and confirm the count still matches the baseline recorded in the Host parity rule. Pass 2's block is added verbatim to both hosts and must contribute **zero** new divergent lines. Same fence-width note as Task 3: the four-backtick wrapper in this plan is quoting, not content.

- [ ] **Step 9: Commit**

```bash
git add templates/claude/code-flow.map.md templates/gemini/code-flow.map.toml templates/copilot/code-flow.map.prompt.md tests/test_template_contracts.py
git commit -m "feat: pass 2 — discover entry points, trace flows, resume across sessions"
```

---

### Task 5: Version 1.1.0 and documentation

**Files:**
- Modify: `package.json`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything Tasks 1-4 produced — the README describes it.
- Produces: nothing later tasks depend on. This is the last task of phase 2.

- [ ] **Step 1: Set the version in both manifests**

In `package.json`, change `"version": "1.0.0"` to `"version": "1.1.0"`.
In `pyproject.toml`, change `version = "1.0.0"` to `version = "1.1.0"`.

`tests/test_packaging.py` already asserts the two agree; there is no new test to write.

- [ ] **Step 2: Run the version test**

Run: `uv run --group dev pytest tests/test_packaging.py -v`

Expected: PASS. A failure here means one manifest was missed.

- [ ] **Step 3: Document whole-codebase mode in the README**

In `README.md`, after the "Usage" section's per-host invocation examples, add:

````markdown
### Whole-codebase mode

Instead of one feature, map the entire repository:

```text
/code-flow.map --whole-code-base
```

This runs two passes. The first walks the repository and catalogues every function
it finds into `Code_Flows/inventory.json`, recording a file census — size and
content hash — in `Code_Flows/index.json`. The second discovers entry points (HTTP
routes, CLI commands, `main()`, event handlers, scheduled jobs, exported API) and
traces each one into its own markdown, HTML and JSON, registering it in the index.

The second pass is the expensive one, and on a large repository it may not finish in
a single session. That is expected and not an error: re-run the command and it skips
the flows already registered in `index.json` and continues. `coverage` in that file
always records what was actually done — if `flowsTraced` is below
`entryPointsFound`, the map is partial and says so.

Whole-codebase mode never edits your source. Feature mode adds docstrings to
undocumented functions as it traces; at repository scale that would be a sweeping
unrequested rewrite, so this mode only reads.

Control how much evidence the catalog carries with `--detail`:

| Level | Each catalogued function carries | Use when |
|---|---|---|
| `thin` | signature, purpose, line count — no code snippet | Very large repositories |
| `standard` (default) | the above plus a snippet capped at ~20 lines | The balanced default |
| `verbose` | the above plus the full function body | Small repositories, or when you want artifacts that stand alone without the source tree |

```text
/code-flow.map --whole-code-base --detail verbose
```

Discovery is search and reading, not a compiler's view of your code. The artifacts
say "catalogued", never "all", and they mean it.
````

- [ ] **Step 4: Update the artifacts list in the README**

Find the section that lists what a run writes and add `Code_Flows/inventory.json` alongside `index.json`, described as: "the function catalog — written by whole-codebase mode only". Keep the existing entries and their wording; this is an addition, not a rewrite.

- [ ] **Step 5: Verify the README's commands against the templates**

Every flag and value the README names must actually appear in all three templates. Check:

```bash
for f in templates/claude/code-flow.map.md templates/gemini/code-flow.map.toml templates/copilot/code-flow.map.prompt.md; do
  echo "--- $f"
  for flag in -- --whole-code-base --detail thin standard verbose inventory.json; do
    grep -q -- "$flag" "$f" && echo "  ok   $flag" || echo "  MISS $flag"
  done
done
```

Expected: no `MISS` lines. A miss means the README promises something a host does not implement — fix the host, not the README.

- [ ] **Step 6: Run the full suite**

Run: `uv run --group dev pytest -v && npm test`

Expected: both pass pristine.

- [ ] **Step 7: End-to-end install check**

Install with both installers into fresh scratch directories and confirm each produces the same four files:

```bash
SCRATCH="$TEMP/cf-phase2"
rm -rf "$SCRATCH" && mkdir -p "$SCRATCH/npm" "$SCRATCH/py"
node bin/install.js --tool all --target "$SCRATCH/npm"
uv run python -m code_flow_skill.cli --tool all --target "$SCRATCH/py"
(cd "$SCRATCH/npm" && find . -type f | sort) > "$SCRATCH/npm.txt"
(cd "$SCRATCH/py"  && find . -type f | sort) > "$SCRATCH/py.txt"
diff "$SCRATCH/npm.txt" "$SCRATCH/py.txt" && echo "IDENTICAL SETS"
cat "$SCRATCH/npm.txt"
diff -r "$SCRATCH/npm" "$SCRATCH/py" && echo "IDENTICAL BYTES"
```

Expected: `IDENTICAL SETS`, `IDENTICAL BYTES`, and exactly these four paths:

```
./.claude/commands/code-flow.map.md
./.code-flow/viewer.template.html
./.gemini/commands/code-flow.map.toml
./.github/prompts/code-flow.map.prompt.md
```

Paste the real listing into your report. Phase 2 adds no installed file — if the count is not four, something reached into the installers that should not have.

- [ ] **Step 8: Commit**

```bash
git add package.json pyproject.toml README.md
git commit -m "release: 1.1.0 — whole-codebase mapping"
```

---

## Deliberate decisions this plan makes beyond the spec

Flag these in review rather than treating them as settled:

1. **Whole-codebase mode never edits source.** The spec does not say. Feature mode's step 3 adds docstrings; applying that across an entire repository would be a large unrequested rewrite, so pass 2 skips step 3 and records `purpose` in the inventory instead.
2. **Pass 1 is resumable via the file census.** The spec makes only pass 2 idempotent. Without a matching rule for pass 1, a repository too large to catalogue in one session can never finish its inventory. The rule reuses data the spec already requires (`files[].size` and `hash`), so it adds no new contract.
3. **The hash has an explicit no-tooling fallback.** An assistant cannot compute SHA-256 by hand. The templates name the platform commands and require `"hash": null` plus a stated limitation when commands are unavailable — never a fabricated value.
4. **`skipReason` gets a closed vocabulary** (`vendored`, `generated`, `binary`, `unparsed`). The spec shows two of these in an example without defining the set; an open vocabulary would make the counts incomparable between runs.

## Known limitation carried forward

No automated check catches a rule that is *present but wrong* in a template — the contract tests assert that field names and key phrases appear in the right region, not that the surrounding rule is correct. That class of defect is caught by the end-to-end host parity read at the close of each task, and by review. This is the same limitation phase 1 disclosed; it has not changed.
