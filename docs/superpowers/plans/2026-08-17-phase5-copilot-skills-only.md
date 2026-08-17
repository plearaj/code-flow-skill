# Phase 5 Implementation Plan — Copilot goes skills-only

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `--tool` a value per supported host, stop installing `.agents/skills/` where nothing reads it, and delete the GitHub Copilot prompt files so Copilot is served by the Agent Skill alone.

**Architecture:** Both installers already copy from two sources — a per-host `toolMap`/`_TOOL_FILES` table and a shared skill installer. This phase splits host *selection* from host *files*: a host may now be selectable without having a table entry, which is exactly what Copilot becomes. `.agents/skills/` stops being unconditional and installs when the selection contains any host that reads it.

**Tech Stack:** Node 18+ (`node --test`), Python 3.11+ (`pytest`), zero dependencies in both.

**Spec:** [`docs/superpowers/specs/2026-08-17-phase5-copilot-skills-only-design.md`](../specs/2026-08-17-phase5-copilot-skills-only-design.md)

## Global Constraints

- **Zero dependencies, including dev.** No `devDependencies` key in `package.json`; the Python dev group stays exactly `pytest>=8.0`.
- **The version becomes `2.0.0`** in `package.json` and `pyproject.toml`, in Task 3 and nowhere else. `tests/test_packaging.py::test_package_versions_match_and_are_1_0_0` currently pins `1.0.0` and is re-pointed in the same task — until then, leave both manifests alone.
- **Every file under `templates/` must use bare LF line endings, never CRLF.** Windows text-mode round-trips have corrupted this repo's templates twice. `tests/test_template_contracts.py::test_shipped_templates_have_no_crlf` checks at the byte level.
- **The two installers must stay in lockstep.** Anything added to `bin/install.js` gets its equivalent in `src/code_flow_skill/cli.py`, including the explanatory comment. The installed-file-set tests in both languages are what holds them there.
- **The installer must be a plain byte copy** — `fs.copyFileSync` / `shutil.copyfile`, never a text-mode read/write round-trip.
- **A contract test must fail when the rule it encodes is deleted.** Every task has a mutation step; run each mutation and report the observed output, not the expected output. A mutation that passes is a dead assertion and a defect to fix before continuing.
- **`--tool <host>` is an explicit request and always installs that host's files.** No heuristic may overrule someone who named a host.
- **Never claim what has not been verified.** Every host statement in the README traces to that host's own documentation; where behaviour is unverified, the docs say so.

## The tool matrix

This table is the contract for Tasks 1 and 2. Task 1 builds every row except Copilot's; Task 2 removes `.github/prompts/` from Copilot's.

| `--tool` | `.claude/commands/` | `.claude/skills/` | `.agents/skills/` | `.gemini/commands/` | `.github/prompts/` | `.code-flow/` |
|---|---|---|---|---|---|---|
| `claude` | yes | yes | — | — | — | yes |
| `copilot` | — | — | yes | — | **Task 1: yes → Task 2: —** | yes |
| `codex` | — | — | yes | — | — | yes |
| `antigravity` | — | — | yes | — | — | yes |
| `gemini` | — | — | yes | yes | — | yes |
| `all` | yes | yes | yes | conditional¹ | Task 1: yes → Task 2: — | yes |

¹ Unchanged: under `--tool all` the Gemini CLI templates install only when the target has its own `.gemini/` directory. `--tool gemini` always installs them.

## File structure

**Deleted (Task 2):**

| Path | Why |
|---|---|
| `templates/copilot/code-flow.map.prompt.md` | Copilot is served by `templates/shared/code-flow-map/SKILL.md` |
| `templates/copilot/code-flow.quality.prompt.md` | same, for the quality command |

**Modified:**

| Path | Change |
|---|---|
| `bin/install.js` | tool selection split from tool files (Task 1); Copilot table entry removed (Task 2) |
| `src/code_flow_skill/cli.py` | the same, in Python |
| `tests/test_installer_python.py` | per-tool expected sets (Task 1); Copilot paths dropped (Task 2) |
| `test/install.test.js` | the same, in Node |
| `tests/test_template_contracts.py` | `MAP_TEMPLATES` / `QUALITY_TEMPLATES` drop Copilot (Task 2) |
| `tests/test_host_parity.py` | `test_every_copilot_prompt_declares_agent_mode` deleted (Task 2) |
| `tests/test_skill_templates.py` | head-contract coverage for anything Copilot's parametrization was guarding (Task 2) |
| `tests/test_packaging.py` | `EXPECTED_IN_WHEEL` drops two paths (Task 2); version test re-pointed (Task 3) |
| `README.md` | per-host table, Usage, manual-install fence, Files-written table, upgrade note (Task 3) |
| `CHANGELOG.md` | `2.0.0` entry (Task 3) |
| `package.json`, `pyproject.toml` | version `2.0.0` (Task 3) |

---

### Task 1: `--tool` learns every host, and `.agents/skills/` stops being unconditional

Copilot keeps its prompt files through this task. That is deliberate: it keeps the diff to one idea, and leaves a working installer at the end of it.

**Files:**
- Modify: `bin/install.js`
- Modify: `src/code_flow_skill/cli.py`
- Modify: `tests/test_installer_python.py`
- Modify: `test/install.test.js`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `VALID_TOOLS` / `_VALID_TOOLS` and `AGENTS_HOSTS` / `_AGENTS_HOSTS` in the two installers, and `EXPECTED_BY_TOOL` in both test suites, all of which Task 2 edits.

- [ ] **Step 1: Write the failing per-tool expectations**

Replace `EXPECTED_ALL` in `tests/test_installer_python.py` with composed pieces plus the matrix. `EXPECTED_ALL` keeps its name and meaning — every path the installer can write — because the README table is checked against it:

```python
_SHARED = [
    ".code-flow/index.template.html",
    ".code-flow/report.template.html",
    ".code-flow/viewer.template.html",
]
_CLAUDE = [
    ".claude/commands/code-flow.map.md",
    ".claude/commands/code-flow.quality.md",
    ".claude/skills/code-flow-map/SKILL.md",
    ".claude/skills/code-flow-quality/SKILL.md",
]
_AGENTS = [
    ".agents/skills/code-flow-map/SKILL.md",
    ".agents/skills/code-flow-map/agents/openai.yaml",
    ".agents/skills/code-flow-quality/SKILL.md",
    ".agents/skills/code-flow-quality/agents/openai.yaml",
]
_GEMINI = [
    ".gemini/commands/code-flow.map.toml",
    ".gemini/commands/code-flow.quality.toml",
]
_COPILOT = [
    ".github/prompts/code-flow.map.prompt.md",
    ".github/prompts/code-flow.quality.prompt.md",
]

# One row per --tool value. This is the contract the two installers are held
# to, and the identical table lives in test/install.test.js.
EXPECTED_BY_TOOL = {
    "claude": sorted(_CLAUDE + _SHARED),
    "copilot": sorted(_AGENTS + _COPILOT + _SHARED),
    "codex": sorted(_AGENTS + _SHARED),
    "antigravity": sorted(_AGENTS + _SHARED),
    "gemini": sorted(_AGENTS + _GEMINI + _SHARED),
}

EXPECTED_ALL = sorted(_CLAUDE + _AGENTS + _GEMINI + _COPILOT + _SHARED)
EXPECTED_WITHOUT_GEMINI = [p for p in EXPECTED_ALL if not p.startswith(".gemini/")]
```

Then add the matrix test:

```python
@pytest.mark.parametrize("tool", sorted(EXPECTED_BY_TOOL))
def test_each_tool_installs_exactly_its_own_set(
    tmp_path: Path, run_python_installer, tool: str
) -> None:
    """Every --tool value writes exactly what that host reads, and nothing else.

    The rows that matter most are `claude`, which must write no
    `.agents/skills/` because Claude Code does not read it, and `codex` /
    `antigravity`, which exist only so those two hosts can be named — before
    this, `.agents/skills/` installed unconditionally because there was no way
    to ask for them.
    """
    run_python_installer(tmp_path, tool=tool)
    assert _installed_paths(tmp_path) == EXPECTED_BY_TOOL[tool]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run --group dev pytest tests/test_installer_python.py -v`

Expected: `test_each_tool_installs_exactly_its_own_set` FAILS for all five rows. `claude` fails with four unexpected `.agents/skills/` paths; `codex` and `antigravity` fail because argparse rejects the value with `SystemExit`.

- [ ] **Step 3: Teach `bin/install.js` the matrix**

Replace the `toolMap` declaration and the selection loop. The two new lists go immediately above `toolMap`:

```js
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
```

Change the validation line inside the `for (const name of selected)` loop from the `toolMap` lookup to the new list, and skip hosts with no files:

```js
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
```

Then make the `.agents` call conditional:

```js
if (selected.includes("claude")) {
  installSkills(".claude", SKILL_FILES);
}
if (selected.some((name) => AGENTS_HOSTS.includes(name))) {
  installSkills(".agents", AGENTS_SKILL_FILES);
}
```

Update the `--tool all` branch so every host is selected. Find the existing selection block and change the two `selected = [...]` lines to:

```js
} else if (geminiIsInUse(target)) {
  selected = ["claude", "copilot", "codex", "antigravity", "gemini"];
} else {
  selected = ["claude", "copilot", "codex", "antigravity"];
  skippedGemini = true;
}
```

Finally update `HELP` so its usage line reads:

```
  code-flow-skill [--target PATH] [--tool claude|copilot|codex|antigravity|gemini|all]
```

- [ ] **Step 4: Teach `src/code_flow_skill/cli.py` the same**

Add above `_TOOL_FILES`:

```python
# Every value --tool accepts. Not the same thing as `_TOOL_FILES` below: a host
# can be selectable without having files of its own. Copilot, Codex and
# Antigravity read `.agents/skills/` and nothing this installer writes
# elsewhere, so they appear here and not there.
_VALID_TOOLS = ("claude", "copilot", "codex", "antigravity", "gemini")

# The hosts that read `.agents/skills/`. Claude Code is deliberately absent:
# its documented skill locations are `~/.claude/skills/`, `.claude/skills/` and
# plugin directories, with no `.agents/` among them, so a Claude-only install
# that wrote there would leave four files nothing reads.
_AGENTS_HOSTS = frozenset({"copilot", "codex", "antigravity", "gemini"})
```

Change `_install_tool` so a host with no table entry is a no-op rather than a `KeyError`. Its loop currently reads `for src_parts, dst_parts in _TOOL_FILES[name]:` — replace that line with:

```python
    # A host with no table entry is served entirely by `.agents/skills/`.
    for src_parts, dst_parts in _TOOL_FILES.get(name, ()):
```

In `main()`, widen the argparse choices and the `all` branches:

```python
    parser.add_argument(
        "--tool",
        default="all",
        choices=[*_VALID_TOOLS, "all"],
        help="Template target to install",
    )
```

```python
    if args.tool != "all":
        selected = [args.tool]
    elif _gemini_is_in_use(target):
        selected = ["claude", "copilot", "codex", "antigravity", "gemini"]
    else:
        selected = ["claude", "copilot", "codex", "antigravity"]
        skipped_gemini = True
```

And make the `.agents` call conditional:

```python
    if "claude" in selected:
        _install_skills(target, ".claude", _SKILL_FILES)
    if _AGENTS_HOSTS.intersection(selected):
        _install_skills(target, ".agents", _AGENTS_SKILL_FILES)
```

`_TOOL_LABELS` is only read for hosts that have files, so it needs no new entries. Leave it alone.

- [ ] **Step 5: Mirror the matrix into the Node suite**

In `test/install.test.js`, replace `EXPECTED_ALL` with the same composition and add the matrix test:

```js
const SHARED = [
  ".code-flow/index.template.html",
  ".code-flow/report.template.html",
  ".code-flow/viewer.template.html",
];
const CLAUDE = [
  ".claude/commands/code-flow.map.md",
  ".claude/commands/code-flow.quality.md",
  ".claude/skills/code-flow-map/SKILL.md",
  ".claude/skills/code-flow-quality/SKILL.md",
];
const AGENTS = [
  ".agents/skills/code-flow-map/SKILL.md",
  ".agents/skills/code-flow-map/agents/openai.yaml",
  ".agents/skills/code-flow-quality/SKILL.md",
  ".agents/skills/code-flow-quality/agents/openai.yaml",
];
const GEMINI = [
  ".gemini/commands/code-flow.map.toml",
  ".gemini/commands/code-flow.quality.toml",
];
const COPILOT = [
  ".github/prompts/code-flow.map.prompt.md",
  ".github/prompts/code-flow.quality.prompt.md",
];

// One row per --tool value. This is the contract the two installers are held
// to, and the identical table lives in tests/test_installer_python.py.
const EXPECTED_BY_TOOL = {
  claude: [...CLAUDE, ...SHARED].sort(),
  copilot: [...AGENTS, ...COPILOT, ...SHARED].sort(),
  codex: [...AGENTS, ...SHARED].sort(),
  antigravity: [...AGENTS, ...SHARED].sort(),
  gemini: [...AGENTS, ...GEMINI, ...SHARED].sort(),
};

const EXPECTED_ALL = [...CLAUDE, ...AGENTS, ...GEMINI, ...COPILOT, ...SHARED].sort();
const EXPECTED_WITHOUT_GEMINI = EXPECTED_ALL.filter((p) => !p.startsWith(".gemini/"));
```

```js
for (const tool of Object.keys(EXPECTED_BY_TOOL).sort()) {
  test(`--tool ${tool} installs exactly its own set`, () => {
    const target = tempTarget();
    runInstaller(target, tool);
    assert.deepEqual(installedPaths(target), EXPECTED_BY_TOOL[tool]);
  });
}
```

- [ ] **Step 6: Run both suites**

```bash
uv run --group dev pytest -q
```

```bash
npm test
```

Expected: both green. Python gains 5 tests, Node gains 5.

- [ ] **Step 7: Mutation proof, five ways**

Each must fail; restore between each and re-run green.

1. In `bin/install.js`, make the `.agents` call unconditional again (drop the `if (selected.some(...))` wrapper). Expected: `npm test` fails `--tool claude installs exactly its own set` with four unexpected `.agents/skills/` paths. **This is the mutation that matters most** — it is the exact behaviour this task exists to change.
2. In `src/code_flow_skill/cli.py`, add `"claude"` to `_AGENTS_HOSTS`. Expected: pytest fails the `claude` row for the same reason.
3. In `src/code_flow_skill/cli.py`, remove `"antigravity"` from `_AGENTS_HOSTS` but leave it in `_VALID_TOOLS`. Expected: pytest fails the `antigravity` row with four missing paths — a host that is selectable but gets nothing.
4. In `bin/install.js`, change the `--tool all` no-Gemini branch back to `["claude", "copilot"]`. Expected: `npm test` fails the existing `--tool all` skip-Gemini test. (It still passes `.agents/` through Copilot, so this checks the *selection*, not the skill install.)
5. In `bin/install.js`, replace `VALID_TOOLS.includes(name)` with the old `hasOwnProperty(toolMap, name)` check. Expected: `npm test` fails the `codex` and `antigravity` rows, which now exit 1 with "Unknown --tool value".

- [ ] **Step 8: Walk it for real**

```bash
rm -rf "$LOCALAPPDATA/Temp/claude/p5" && mkdir -p "$LOCALAPPDATA/Temp/claude/p5/claude" "$LOCALAPPDATA/Temp/claude/p5/codex" && node bin/install.js --target "$LOCALAPPDATA/Temp/claude/p5/claude" --tool claude >/dev/null && uv run python -m code_flow_skill.cli --target "$LOCALAPPDATA/Temp/claude/p5/codex" --tool codex >/dev/null && find "$LOCALAPPDATA/Temp/claude/p5" -type f | sed "s|.*p5/||" | sort
```

Expected: the `claude/` tree has `.claude/` and `.code-flow/` and **no `.agents/`**; the `codex/` tree has `.agents/` and `.code-flow/` and **no `.claude/`**. Read the output rather than trusting the exit code.

- [ ] **Step 9: Commit**

```bash
git add bin/install.js src/code_flow_skill/cli.py tests/test_installer_python.py test/install.test.js
git commit -m "feat: give --tool a value per host, and install .agents/skills only where it is read"
```

---

### Task 2: Delete the Copilot prompt files

**Files:**
- Delete: `templates/copilot/code-flow.map.prompt.md`
- Delete: `templates/copilot/code-flow.quality.prompt.md`
- Modify: `bin/install.js`, `src/code_flow_skill/cli.py`
- Modify: `tests/test_installer_python.py`, `test/install.test.js`
- Modify: `tests/test_template_contracts.py`, `tests/test_host_parity.py`, `tests/test_packaging.py`
- Modify: `tests/test_skill_templates.py`

**Interfaces:**
- Consumes: `EXPECTED_BY_TOOL`, `VALID_TOOLS`/`_VALID_TOOLS`, `AGENTS_HOSTS`/`_AGENTS_HOSTS` from Task 1.
- Produces: nothing later tasks read in code; Task 3 documents the outcome.

- [ ] **Step 1: Check what coverage the Copilot parametrization was carrying**

Before deleting anything, find out what only Copilot's rows were guarding. Run:

```bash
uv run --group dev pytest -q --collect-only 2>/dev/null | grep -c copilot
```

Expected: 64. Then read `MAP_TEMPLATES` and `QUALITY_TEMPLATES` in `tests/test_template_contracts.py`. Every test parametrized over them asserts a rule about *content* — the honesty phrasings, the detector thresholds, the step-6 index fields.

Those rules survive for Claude and Gemini, and the skill inherits them through `tests/test_skill_templates.py::test_skill_body_is_derived_from_the_gemini_template` — **but only for the body.** `derive_skill_body` slices from `#### 1.` onward, so anything stated in a template's hand-written head is not covered by derivation. Phase 4 found exactly one such rule (`never edits source code`) shipping untested for this reason.

Read the head of `templates/shared/code-flow-quality/SKILL.md` and `templates/shared/code-flow-map/SKILL.md` — everything above `#### 1.` — and list every factual claim or rule stated there. For each, check whether `tests/test_skill_templates.py` already asserts it. Record the list in your report. If any rule is unasserted, add a test for it in Step 6 rather than leaving it to review.

- [ ] **Step 2: Delete the templates and drop Copilot from the installers**

```bash
git rm templates/copilot/code-flow.map.prompt.md templates/copilot/code-flow.quality.prompt.md
```

In `bin/install.js`, delete the `copilot:` entry from `toolMap`, leaving `claude` and `gemini`. **Do not** remove `"copilot"` from `VALID_TOOLS` — it stays selectable and is now served entirely by `.agents/skills/`. Amend the comment above `toolMap` to say so:

```js
// The hosts that install files of their own, one per command. Copilot is not
// here: its prompt files were removed in 2.0.0 and it reads `.agents/skills/`
// like every other skill-only host. This list and the one in
// src/code_flow_skill/cli.py must stay in step; the installed-file-set tests
// in both languages are what holds them there.
```

In `src/code_flow_skill/cli.py`, delete the `"copilot"` key from `_TOOL_FILES` and the `"copilot"` entry from `_TOOL_LABELS`, and carry the same comment.

- [ ] **Step 3: Shrink the expected sets**

In `tests/test_installer_python.py`, delete the `_COPILOT` list and both of its uses:

```python
EXPECTED_BY_TOOL = {
    "claude": sorted(_CLAUDE + _SHARED),
    "copilot": sorted(_AGENTS + _SHARED),
    "codex": sorted(_AGENTS + _SHARED),
    "antigravity": sorted(_AGENTS + _SHARED),
    "gemini": sorted(_AGENTS + _GEMINI + _SHARED),
}

EXPECTED_ALL = sorted(_CLAUDE + _AGENTS + _GEMINI + _SHARED)
```

Make the identical change in `test/install.test.js` (delete `COPILOT`, drop it from `copilot:` and `EXPECTED_ALL`).

Delete `test_copilot_install_does_not_touch_instructions_file` from `tests/test_installer_python.py` and `copilot install leaves copilot-instructions.md untouched` from `test/install.test.js`: both assert the installer leaves `.github/copilot-instructions.md` alone, which was only ever interesting because the installer used to edit it and then wrote a prompt file next to it. It now writes nothing under `.github/` at all — Step 5's absence test is the stronger statement.

Delete `test_installs_copilot_prompt_file` (`tests/test_installer_python.py:127`) — it asserts a file that no longer exists.

`test_selecting_one_tool_installs_both_of_its_commands` (`tests/test_installer_python.py:154`) is built entirely on Copilot's prompt files and cannot survive as written — Copilot no longer *has* two commands of its own. **Re-point it at Gemini rather than deleting it**, because the property it checks is still worth having: that selecting one host installs both of that host's commands and none of another's.

```python
def test_selecting_one_tool_installs_both_of_its_commands(
    tmp_path: Path, run_python_installer
) -> None:
    """Re-pointed from Copilot to Gemini in 2.0.0. Copilot no longer installs
    commands of its own — it reads the Agent Skill — so Gemini is now the
    smallest host that still has a pair of command files to check."""
    run_python_installer(tmp_path, tool="gemini")
    commands = tmp_path / ".gemini" / "commands"
    assert (commands / "code-flow.map.toml").is_file()
    assert (commands / "code-flow.quality.toml").is_file()
    assert not (tmp_path / ".claude").exists()
    assert not (tmp_path / ".github").exists()
```

Then grep both test files for `prompts/` and `copilot-instructions` and remove every remaining reference.

- [ ] **Step 4: Drop Copilot from the content contracts**

In `tests/test_template_contracts.py`:

```python
MAP_TEMPLATES = (
    ("claude", "code-flow.map.md"),
    ("gemini", "code-flow.map.toml"),
)
```

```python
QUALITY_TEMPLATES = (
    ("claude", "code-flow.quality.md"),
    ("gemini", "code-flow.quality.toml"),
)
```

Several region-anchor regexes in that module carry a Copilot alternative — for example `_INDEX_SECTION_END = re.compile(r"\n(?:#### 7\.|7\.\s*\*\*Report)")` and `_DETECTORS_END = re.compile(r"\n(?:#### 4\.|4\.\s*\*\*)")`. **Leave every one of them exactly as it is.** They are harmless with two hosts, and their comments record why the Copilot alternative was written the way it was — evidence a future reader needs if a third host is ever added back. Removing them is a silent loss of reasoning for no gain.

In `tests/test_host_parity.py`, delete `test_every_copilot_prompt_declares_agent_mode` entirely, including its docstring. It asserts a property of files that no longer exist.

In `tests/test_packaging.py`, remove these two entries from `EXPECTED_IN_WHEEL`:

```python
    "code_flow_skill/templates/copilot/code-flow.map.prompt.md",
    "code_flow_skill/templates/copilot/code-flow.quality.prompt.md",
```

- [ ] **Step 5: Assert the directory is gone and stays gone**

Append to `tests/test_template_contracts.py`:

```python
def test_no_copilot_template_directory(repo_root: Path) -> None:
    """Copilot's prompt files were removed in 2.0.0; it is served by the Agent
    Skill alone.

    This is a tombstone, not a tidiness check. A half-finished revert that
    restored `templates/copilot/` without restoring the installer entry would
    ship two dead files inside both packages — `package.json`'s `files` list and
    hatch's force-include both take `templates/` wholesale, so anything left in
    that directory is published whether or not any code copies it.
    """
    assert not (repo_root / "templates" / "copilot").exists(), (
        "templates/copilot/ is back; Copilot is served by "
        "templates/shared/code-flow-*/SKILL.md, and anything under templates/ "
        "ships in both packages whether or not the installer copies it"
    )
```

- [ ] **Step 6: Cover any head rule Step 1 found unasserted**

If Step 1 found a rule stated in a `SKILL.md` head with no test, add one now, scoped to the head using the existing `_head(repo_root, skill_dir)` helper in `tests/test_skill_templates.py`. Follow the shape of the test that already lives there:

```python
def test_quality_skill_never_writes_source(repo_root: Path) -> None:
    head = _head(repo_root, "code-flow-quality")
    assert re.search(r"never edits source code", head, re.IGNORECASE), (
        "the quality skill's head no longer states that it never edits source code"
    )
```

If Step 1 found nothing unasserted, write that finding in your report and skip this step — do not invent a test to have something to add here.

- [ ] **Step 7: Run both suites**

```bash
uv run --group dev pytest -q
```

```bash
npm test
```

Expected: Python drops by roughly 34 (the Copilot parametrizations across both contract sets, the parity test, and the two installer tests) and gains 1 from Step 5; Node drops by 2. Report the actual numbers.

- [ ] **Step 8: Mutation proof, three ways**

1. Recreate `templates/copilot/` with a single empty file. Expected: `pytest tests/test_template_contracts.py -v` fails `test_no_copilot_template_directory`. Remove it.
2. Add `"copilot"` back to `_TOOL_FILES` in `src/code_flow_skill/cli.py` pointing at the deleted templates. Expected: pytest fails the `copilot` row of `test_each_tool_installs_exactly_its_own_set` — with `FileNotFoundError`, since the source files are gone. Restore.
3. Remove `"copilot"` from `VALID_TOOLS` in `bin/install.js`. Expected: `npm test` fails `--tool copilot installs exactly its own set`, which must still pass — Copilot stays selectable. Restore.

- [ ] **Step 9: Confirm the packages no longer carry the templates**

```bash
npm pack --dry-run 2>&1 | grep -c "templates/copilot"
```

Expected: `0`.

- [ ] **Step 10: Commit**

```bash
git add -A templates bin src tests test
git commit -m "feat!: remove the Copilot prompt files; Copilot is served by the Agent Skill"
```

---

### Task 3: Docs, and the version

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `package.json`, `pyproject.toml`
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Consumes: the installed sets from Tasks 1 and 2.
- Produces: nothing.

- [ ] **Step 1: Re-point the version test, then bump both manifests**

In `tests/test_packaging.py`, rename `test_package_versions_match_and_are_1_0_0` to `test_package_versions_match_and_are_2_0_0` and change the expected string from `"1.0.0"` to `"2.0.0"`. Run it and watch it fail:

```bash
uv run --group dev pytest tests/test_packaging.py -v
```

Expected: FAIL, both manifests still say `1.0.0`.

Then set `"version": "2.0.0"` in `package.json` and `version = "2.0.0"` in `pyproject.toml`, and re-run. Expected: PASS.

- [ ] **Step 2: Fix the README's per-host table**

The table under the lede currently gives Copilot a command form. Replace that row:

```markdown
| GitHub Copilot | — | `/code-flow-map` |
```

And amend the sentence below the table, which currently says "Three hosts read both forms; three read only the skill", to:

```markdown
because the skill format forbids dots in a name. Two hosts read both forms; four
read only the skill:
```

- [ ] **Step 3: Rewrite the README's Copilot usage block**

Under `## Usage`, replace the whole **GitHub Copilot** block — from the `**GitHub Copilot**` heading through the paragraph beginning "**If you don't use Copilot in VS Code**" — with:

```markdown
**GitHub Copilot**

```text
/code-flow-map user login
```

Copilot reads the Agent Skill from `.agents/skills/`. It has no prompt file: the
`.github/prompts/*.prompt.md` files that 0.x and 1.0 installed were removed in
2.0.0, because [VS Code's own documentation](https://code.visualstudio.com/docs/copilot/customization/prompt-files)
says agents on the Agent Host do not use prompt files and to convert them to
skills. If you upgraded, delete `.github/prompts/code-flow.map.prompt.md` and
`.github/prompts/code-flow.quality.prompt.md` by hand — the installer does not
remove what it previously wrote.
```

- [ ] **Step 4: Fix the manual-install fence and the Verify step**

In `### Manual install (no npm, no uvx)`, delete the `# GitHub Copilot` block and its two `cp` lines, and delete `.github/prompts` from the `mkdir -p` above them.

In the `**3. Verify.**` paragraph, replace the Copilot clause — "For Copilot in VS Code, look for both prompts in the Prompts picker (or try `/code-flow.map` in chat), and both skills alongside them; on other Copilot surfaces, see the **GitHub Copilot** notes under *Usage*." — with:

```markdown
In Copilot, look for the skills `/code-flow-map` and `/code-flow-quality`; there are no longer any prompt files to find.
```

- [ ] **Step 5: Fix the Files-written table and the `--tool` documentation**

Delete the two `GitHub Copilot` rows from the `## Files written` table — the test `test_readme_files_written_table_lists_exactly_the_installed_set` compares it against `EXPECTED_ALL` and will fail until you do.

Replace the `## CLI options` usage line with:

```text
code-flow-skill [--target PATH] [--tool claude|copilot|codex|antigravity|gemini|all]
```

And add, immediately below that block:

```markdown
`--tool` now names every supported host. `claude` writes `.claude/` and the shared
scaffolds and nothing else — Claude Code does not read `.agents/skills/`, so a
Claude-only project no longer gets four files nothing there opens. `copilot`,
`codex` and `antigravity` write `.agents/skills/`, which is the whole of their
integration. `gemini` adds its own `.gemini/commands/` on top.

One consequence worth knowing if you use Copilot: **`--tool copilot` writes the
skill exactly once.** Only `--tool all` puts it in both `.claude/skills/` and
`.agents/skills/`, which are both directories Copilot scans.
```

Then find the paragraph under `## Skills and commands` that begins "**On Copilot, the same skill lands in two directories it both scans.**" and change its final sentence from "`--tool copilot` writes only `.agents/skills/`, which sidesteps the question if Copilot is the only host you use." to "`--tool copilot` writes only `.agents/skills/`, so a Copilot-only install sidesteps the question entirely."

- [ ] **Step 6: Add the 1.0 → 2.0 upgrade note**

At the top of `## Upgrading from 0.x to 1.0`, change the heading to `## Upgrading` and insert before the existing content:

```markdown
### 1.0 to 2.0

**The Copilot prompt files are gone.** `.github/prompts/code-flow.map.prompt.md`
and `.github/prompts/code-flow.quality.prompt.md` are no longer installed, and
the installer does not delete what it previously wrote — remove them by hand.
Copilot is served by the Agent Skill at `.agents/skills/code-flow-map/`, which
1.0 already installed, so **if you installed 1.0 you already have the
replacement.** Invoke it as `/code-flow-map` rather than `/code-flow.map`.

**`--tool` gained `codex` and `antigravity`**, and no longer writes
`.agents/skills/` for a Claude-only install. Re-running the installer with
`--tool claude` will not remove an `.agents/skills/` directory an earlier version
created; delete it by hand if you want it gone.

### 0.x to 1.0
```

- [ ] **Step 7: Write the CHANGELOG entry**

At the top of `CHANGELOG.md`, immediately below the intro paragraph and above `## [1.0.0]`:

```markdown
## [2.0.0]

### Removed — breaking

- **The GitHub Copilot prompt files.** `.github/prompts/code-flow.map.prompt.md`
  and `.github/prompts/code-flow.quality.prompt.md` are no longer installed.
  Copilot is served by the Agent Skill at `.agents/skills/`, which `1.0.0`
  already installed. VS Code's own documentation says agents on the Agent Host
  do not use prompt files and to convert them to skills, and this project never
  verified that the dotted prompt-file name was exposed as a `/`-command at all.
  The installer does not delete what it previously wrote; remove the two files by
  hand. **See "Upgrading" in the README.**

### Changed

- **`--tool` names every supported host**: `claude`, `copilot`, `codex`,
  `antigravity`, `gemini`, `all`. `codex` and `antigravity` are new, and exist
  because `.agents/skills/` used to install unconditionally purely for want of a
  way to ask for those two hosts.
- **`--tool claude` no longer writes `.agents/skills/`.** Claude Code reads
  `.claude/skills/` and not `.agents/`, so those four files were never opened by
  anything in a Claude-only project.
- **`--tool copilot` now writes the skill exactly once**, under `.agents/skills/`
  only. Only `--tool all` places it in both directories Copilot scans.

### Note on the release cadence

`2.0.0` follows `1.0.0` by a day. Removing an installed integration is a breaking
change whatever its age, and `1.0.0`'s own design document had already scheduled
this removal for "a later major version" — that document simply expected more
time to pass. Nothing in `1.0.0` was withdrawn from the registry.
```

- [ ] **Step 8: Run both suites**

```bash
uv run --group dev pytest -q
```

```bash
npm test
```

Expected: both green, including `test_readme_files_written_table_lists_exactly_the_installed_set` and the renamed version test.

- [ ] **Step 9: Mutation proof, two ways**

1. Add a `| GitHub Copilot | `/code-flow.map` | `.github/prompts/code-flow.map.prompt.md` |` row back to the README's Files-written table. Expected: pytest fails `test_readme_files_written_table_lists_exactly_the_installed_set` naming the extra path. Remove it.
2. Set `"version": "2.0.1"` in `package.json` only. Expected: pytest fails `test_package_versions_match_and_are_2_0_0` on the mismatch between the two manifests. Restore.

- [ ] **Step 10: Check the release gate still describes reality**

Run:

```bash
node scripts/prepublish-check.js
```

Read checklist item 4. It names the hosts a maintainer may pick and tells them to confirm the skill is listed. It does not mention prompt files, so it needs no edit — but **confirm that by reading it**, and say so in your report. If it does mention them, fix it.

- [ ] **Step 11: Commit**

```bash
git add README.md CHANGELOG.md package.json pyproject.toml tests/test_packaging.py
git commit -m "docs: document the Copilot removal and the per-host --tool, and bump to 2.0.0"
```

---

## Before this ships

**`2.0.0` must not be published until a human has confirmed `/code-flow-map` loads in GitHub Copilot.** Phase 4's Decision 6 conditioned removing a host's command files on the skills being "confirmed working against all three hosts in the wild", and that has not happened for Copilot. Until it does, this phase deletes the only other thing that served Copilot on the strength of documentation alone. `scripts/prepublish-check.js` item 4 asks for exactly this observation; it must be done on **Copilot specifically** for this release, not on whichever host is most convenient.

That check is the release gate, not a task in this plan, and no test in this repository can stand in for it.
