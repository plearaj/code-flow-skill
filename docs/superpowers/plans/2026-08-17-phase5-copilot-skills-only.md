# Phase 5 Implementation Plan — `--tool` learns every host

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `--tool` a value per supported host, and stop installing `.agents/skills/` into projects where nothing reads it.

**Architecture:** Both installers already copy from two sources — a per-host `toolMap`/`_TOOL_FILES` table and a shared skill installer. This phase splits host *selection* from host *files*, so a host can be selectable without having a table entry of its own — which is what Codex and Antigravity are. `.agents/skills/` stops being unconditional and installs when the selection contains a host that reads it.

**Scope note:** an earlier revision of this plan also deleted the Copilot prompt files. That was overturned by direct observation before any of it was written — see the spec's Decision 1. `templates/copilot/` stays, and so does every test parametrized over it.

**Tech Stack:** Node 18+ (`node --test`), Python 3.11+ (`pytest`), zero dependencies in both.

**Spec:** [`docs/superpowers/specs/2026-08-17-phase5-copilot-skills-only-design.md`](../specs/2026-08-17-phase5-copilot-skills-only-design.md)

## Global Constraints

- **Zero dependencies, including dev.** No `devDependencies` key in `package.json`; the Python dev group stays exactly `pytest>=8.0`.
- **The version becomes `1.1.0`** in `package.json` and `pyproject.toml`, in Task 2 and nowhere else. `tests/test_packaging.py::test_package_versions_match_and_are_1_0_0` currently pins `1.0.0` and is re-pointed in the same task — until then, leave both manifests alone.
- **Every file under `templates/` must use bare LF line endings, never CRLF.** Windows text-mode round-trips have corrupted this repo's templates twice. `tests/test_template_contracts.py::test_shipped_templates_have_no_crlf` checks at the byte level.
- **The two installers must stay in lockstep.** Anything added to `bin/install.js` gets its equivalent in `src/code_flow_skill/cli.py`, including the explanatory comment. The installed-file-set tests in both languages are what holds them there.
- **The installer must be a plain byte copy** — `fs.copyFileSync` / `shutil.copyfile`, never a text-mode read/write round-trip.
- **A contract test must fail when the rule it encodes is deleted.** Every task has a mutation step; run each mutation and report the observed output, not the expected output. A mutation that passes is a dead assertion and a defect to fix before continuing.
- **`--tool <host>` is an explicit request and always installs that host's files.** No heuristic may overrule someone who named a host.
- **Never claim what has not been verified.** Every host statement in the README traces to that host's own documentation; where behaviour is unverified, the docs say so.

## The tool matrix

This table is Task 1's contract, and Task 2 documents it.

| `--tool` | `.claude/commands/` | `.claude/skills/` | `.agents/skills/` | `.gemini/commands/` | `.github/prompts/` | `.code-flow/` |
|---|---|---|---|---|---|---|
| `claude` | yes | yes | — | — | — | yes |
| `copilot` | — | — | yes | — | yes | yes |
| `codex` | — | — | yes | — | — | yes |
| `antigravity` | — | — | yes | — | — | yes |
| `gemini` | — | — | yes | yes | — | yes |
| `all` | yes | yes | yes | conditional¹ | yes | yes |

¹ Unchanged: under `--tool all` the Gemini CLI templates install only when the target has its own `.gemini/` directory. `--tool gemini` always installs them.

`copilot` keeps **both** rows, and that is the point of the phase's correction: VS Code Copilot Chat reads the prompt file, the Copilot CLI reads the skill, and both were observed working on 2026-08-17. One `--tool` value, two surfaces, two files.

## File structure

**Nothing is created or deleted.** No template changes at all — this phase is installer logic and documentation.

**Modified:**

| Path | Change |
|---|---|
| `bin/install.js` | tool selection split from tool files; `.agents/skills/` conditional (Task 1) |
| `src/code_flow_skill/cli.py` | the same, in Python (Task 1) |
| `tests/test_installer_python.py` | `EXPECTED_BY_TOOL` and the matrix test (Task 1) |
| `test/install.test.js` | the same, in Node (Task 1) |
| `README.md` | the two Copilot surfaces, the new `--tool` values, and the retired caveat (Task 2) |
| `CHANGELOG.md` | `1.1.0` entry (Task 2) |
| `package.json`, `pyproject.toml` | version `1.1.0` (Task 2) |
| `tests/test_packaging.py` | version test re-pointed (Task 2) |

---

### Task 1: `--tool` learns every host, and `.agents/skills/` stops being unconditional

Copilot keeps its prompt files. `--tool copilot` writes them *and* `.agents/skills/`, because VS Code Copilot Chat reads the first and the Copilot CLI reads the second.

**Files:**
- Modify: `bin/install.js`
- Modify: `src/code_flow_skill/cli.py`
- Modify: `tests/test_installer_python.py`
- Modify: `test/install.test.js`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `VALID_TOOLS` / `_VALID_TOOLS` and `AGENTS_HOSTS` / `_AGENTS_HOSTS` in the two installers, and `EXPECTED_BY_TOOL` in both test suites. Task 2 documents the matrix they encode but does not edit them.

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

### Task 2: Docs, and the version

The documentation change is the larger half of this task, and it is not the `--tool` values. It is that **Copilot is two surfaces reading two different files**, which this project did not know until 2026-08-17 and which explains the naming inconsistency the README has been apologising for since 1.0.

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `package.json`, `pyproject.toml`
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Consumes: the per-tool installed sets from Task 1.
- Produces: nothing.

- [ ] **Step 1: Re-point the version test, then bump both manifests**

In `tests/test_packaging.py`, rename `test_package_versions_match_and_are_1_0_0` to `test_package_versions_match_and_are_1_1_0` and change the expected string from `"1.0.0"` to `"1.1.0"`. Run it and watch it fail:

```bash
uv run --group dev pytest tests/test_packaging.py -v
```

Expected: FAIL, both manifests still say `1.0.0`.

Then set `"version": "1.1.0"` in `package.json` and `version = "1.1.0"` in `pyproject.toml`, and re-run. Expected: PASS.

- [ ] **Step 2: Split Copilot into its two surfaces in the lede table**

The table under the lede currently has one Copilot row claiming a VS-Code-only caveat. Replace that single row with two:

```markdown
| GitHub Copilot (VS Code Chat) | `/code-flow.map` | — |
| GitHub Copilot (CLI) | — | `/code-flow-map` |
```

Then replace the sentence below the table that reads "Three hosts read both forms; three read only the skill:" with:

```markdown
because the skill format forbids dots in a name. Which one you get depends on
what your host reads — and **GitHub Copilot is two hosts**, not one:
```

And replace the paragraph beginning "If a row shows no command form" with:

```markdown
If a row shows only one form, that host reads only one file. **VS Code Copilot
Chat reads the prompt file** at `.github/prompts/`, where Agent Skills are still
an experimental feature; **the Copilot CLI reads the skill** at `.agents/skills/`,
where VS Code's documentation says prompt files are not used at all. Both were
observed working on 2026-08-17. Both forms read and write the same `Code_Flows/`
artifacts, so a flow mapped by one is readable by the other.
```

- [ ] **Step 3: Retire the unverified caveat, because it is now verified**

Under `## Usage`, the **GitHub Copilot** block contains this paragraph:

> Two things this project has **not** verified and therefore does not claim: that Copilot Chat exposes a *dotted* filename as a `/`-command (the `code-flow.map` name follows the [GitHub Spec Kit](https://github.com/github/spec-kit) prompt-file naming convention rather than any confirmed Copilot behavior), and whether Copilot surfaces other than VS Code read prompt files at all. If the slash form doesn't appear, use the Prompts picker.

Replace it with:

```markdown
**Verified 2026-08-17** on VS Code 1.132.0 with Copilot Chat 0.35.3: `/code-flow.map`
appears in chat and runs. The dotted name follows the [GitHub Spec Kit](https://github.com/github/spec-kit)
prompt-file convention, and Copilot Chat does expose it as a `/`-command. That is one
observation on one machine, not a guarantee for every version — if the slash form
doesn't appear for you, use the Prompts picker.

**In the Copilot CLI, use the skill instead:** `/code-flow-map`. The CLI is an Agent
Host, and [VS Code's documentation](https://code.visualstudio.com/docs/copilot/customization/prompt-files)
says agents on the Agent Host do not use prompt files. Skills in VS Code Chat are the
mirror image — an [experimental feature](https://code.visualstudio.com/docs/agent-customization/agent-skills)
added in 1.108 — so at present each Copilot surface has exactly one working form, and
this package installs both.
```

Leave the paragraph beginning "**If you don't use Copilot in VS Code**" exactly as it is. It covers github.com, JetBrains and Visual Studio, none of which were tested, and its advice is unchanged.

- [ ] **Step 4: Document the new `--tool` values**

Replace the `## CLI options` usage line with:

```text
code-flow-skill [--target PATH] [--tool claude|copilot|codex|antigravity|gemini|all]
```

And add, immediately below that block:

```markdown
`--tool` names every supported host. `claude` writes `.claude/` and the shared
scaffolds and nothing else — Claude Code does not read `.agents/skills/`, so a
Claude-only project no longer gets four files nothing there opens. `codex` and
`antigravity` write `.agents/skills/`, which is the whole of their integration.
`copilot` writes `.agents/skills/` **and** `.github/prompts/`, because its two
surfaces read different files. `gemini` adds `.gemini/commands/` on top.

**If you upgraded from 1.0 and used `--tool claude`,** re-running the installer will
not remove an `.agents/skills/` directory that an earlier version created. Delete it
by hand if you want it gone; nothing on Claude Code reads it either way.
```

- [ ] **Step 5: Fix the Copilot double-write paragraph**

Under `## Skills and commands`, find the paragraph beginning "**On Copilot, the same skill lands in two directories it both scans.**" and change its final sentence from "`--tool copilot` writes only `.agents/skills/`, which sidesteps the question if Copilot is the only host you use." to:

```markdown
`--tool copilot` writes the skill to `.agents/skills/` only, so a Copilot-only install
sidesteps the question entirely.
```

The rest of that paragraph is unchanged and still correct: `--tool all` does put the skill in both directories Copilot scans, and Copilot's docs still say nothing about precedence.

- [ ] **Step 6: Write the CHANGELOG entry**

At the top of `CHANGELOG.md`, immediately below the intro paragraph and above `## [1.0.0]`:

```markdown
## [1.1.0]

### Added

- **`--tool` names every supported host**: `claude`, `copilot`, `codex`, `antigravity`,
  `gemini`, `all`. `codex` and `antigravity` are new — `.agents/skills/` used to install
  unconditionally purely for want of a way to ask for those two hosts.

### Changed

- **`--tool claude` no longer writes `.agents/skills/`.** Claude Code reads
  `.claude/skills/` and not `.agents/`, so those four files were never opened by anything
  in a Claude-only project. Re-running the installer does not remove an `.agents/skills/`
  directory an earlier version created.

### Documentation — and one thing this project got wrong

- **GitHub Copilot is two surfaces, not one, and they read different files.** VS Code
  Copilot Chat reads `.github/prompts/*.prompt.md` and answers to `/code-flow.map`; the
  Copilot CLI reads `.agents/skills/` and answers to `/code-flow-map`. Both were observed
  working on 2026-08-17 (VS Code 1.132.0, Copilot Chat 0.35.3, Copilot CLI 1.0.10). The
  README presented one Copilot where there are two, which is why its naming looked
  inconsistent.
- **The caveat that `1.0.0` shipped about the dotted prompt-file name is retired.** It
  said this project had "not verified and therefore does not claim" that Copilot Chat
  exposes a dotted filename as a `/`-command. It does.
- A planned `2.0.0` would have **deleted** the Copilot prompt files on the reasoning that
  the skill had replaced them. It had not: skills in VS Code Chat are still experimental
  and did not load, so that release would have left VS Code Copilot users with nothing.
  The plan was overturned before implementation by ten minutes of opening both surfaces.
  See `docs/superpowers/specs/2026-08-17-phase5-copilot-skills-only-design.md`.
```

- [ ] **Step 7: Run both suites**

```bash
uv run --group dev pytest -q
```

```bash
npm test
```

Expected: both green, including `test_readme_files_written_table_lists_exactly_the_installed_set` — the Files-written table is unchanged by this task, because nothing was added to or removed from what the installer can write.

- [ ] **Step 8: Mutation proof, two ways**

1. Set `"version": "1.1.1"` in `package.json` only. Expected: pytest fails `test_package_versions_match_and_are_1_1_0` on the mismatch between the two manifests. Restore.
2. Delete one `.agents/skills/` row from the README's Files-written table. Expected: pytest fails `test_readme_files_written_table_lists_exactly_the_installed_set` naming the missing path. Restore. (This confirms the table test is still live after Task 1 changed how the paths are composed.)

- [ ] **Step 9: Check the release gate still describes reality**

Run:

```bash
node scripts/prepublish-check.js
```

Read checklist item 4. It tells the maintainer to pick a host and confirm the skill is listed, and names the per-host invocation forms. **It currently implies one Copilot.** Amend the Copilot clause so it names both surfaces and says which form to expect on each — a maintainer who checks VS Code Chat for `/code-flow-map` will find nothing and wrongly conclude the release is broken, which is precisely the confusion this phase exists to clear up.

Then add `assert.match(r.stdout, /Copilot CLI/i, "checklist does not distinguish the two Copilot surfaces");` to the checklist test in `test/prepublish-check.test.js`, run `npm test`, and mutation-prove it by deleting the clause.

- [ ] **Step 10: Commit**

```bash
git add README.md CHANGELOG.md package.json pyproject.toml tests/test_packaging.py scripts/prepublish-check.js test/prepublish-check.test.js
git commit -m "docs: document the two Copilot surfaces and the per-host --tool, and bump to 1.1.0"
```

---

## Before this ships

**Nothing here is release-blocked.** The gate that governed the previous revision of this plan — confirming the skill works on Copilot before deleting the prompt files — was run, and it is what overturned that plan. Nothing is being removed now, so no host can end up with less than it has today.

Two things are worth doing anyway before publishing `1.1.0`:

- **Re-run the manual browser pass.** `scripts/prepublish-check.js` items 1–3 cover the three HTML scaffolds, which no test in this repository renders. They are unchanged by this phase, but the gate does not track that and the checklist is cheap.
- **Install into a real project with `--tool claude` and confirm no `.agents/` appears.** It is the one behaviour this phase takes away, and the tests assert it in a temp directory rather than in a project that already has one.
