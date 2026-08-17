# Phase 5 Implementation Plan — per-host `--tool`, a bundled page, and user themes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `--tool` a value per supported host; let a user theme every generated page; and add one self-contained bundled page they can hand to someone, with a flag choosing whether the loose pages come too.

**Architecture:** Both installers already copy from two sources — a per-host `toolMap`/`_TOOL_FILES` table and a shared skill installer. This phase splits host *selection* from host *files*, so a host can be selectable without having a table entry of its own — which is what Codex and Antigravity are. `.agents/skills/` stops being unconditional and installs when the selection contains a host that reads it.

**The HTML half** leans on what the scaffolds already are. All three drive every colour through ~25 CSS custom properties in a `:root{}` block with a `[data-theme="light"]{}` override, so a user theme is those same properties with different values, inlined through a new `__THEME_CSS__` token. The bundle is a fourth scaffold composed from the three existing ones, rebuilt from the JSON artifacts on every run exactly as `index.html` already is — never patched in place.

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

**Nothing is deleted.** `templates/copilot/` stays, and so does every test parametrized over it.

**Created:**

| Path | Responsibility |
|---|---|
| `templates/shared/theme.css` | Every custom property at its current default, commented out, in both a `:root` and a `[data-theme="light"]` block. A menu the user opts into. |
| `templates/shared/bundle.template.html` | One self-contained page carrying the index, every flow and the quality report. Two tokens: `__BUNDLE_DATA__`, `__THEME_CSS__`. |
| `tests/test_theme.py` | The theme token's position and the shipped file's shape — the parts of theming that are checkable without rendering anything. |

**Modified:**

| Path | Change |
|---|---|
| `bin/install.js` | tool selection split from tool files, `.agents/skills/` conditional (Task 1); two new shared files (Tasks 2, 3) |
| `src/code_flow_skill/cli.py` | the same, in Python |
| `tests/test_installer_python.py` | `EXPECTED_BY_TOOL` and the matrix test (Task 1); `_SHARED` grows twice (Tasks 2, 3) |
| `test/install.test.js` | the same, in Node |
| `templates/shared/{viewer,report,index}.template.html` | `__THEME_CSS__` after the light-palette block (Task 2) |
| `test/viewer-validation.test.js` | the bundle scaffold's `validate()` cases (Task 3) |
| `templates/{claude,gemini,copilot}/*` ×6 | `--output` and the theme rule, in each host's register (Task 4) |
| `templates/shared/code-flow-*/SKILL.md` | regenerated from Gemini, not hand-edited (Task 4) |
| `tests/test_template_contracts.py` | `--output`, JSON-always, and theme-inlining contracts (Task 4) |
| `tests/test_packaging.py` | two new wheel paths (Tasks 2, 3); version test re-pointed (Task 5) |
| `README.md` | Copilot's two surfaces, the new `--tool` values, `--output`, theming (Task 5) |
| `CHANGELOG.md` | `1.1.0` entry (Task 5) |
| `package.json`, `pyproject.toml` | version `1.1.0` (Task 5) |
| `scripts/prepublish-check.js`, `test/prepublish-check.test.js` | a fourth scaffold to open by hand (Task 5) |

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

### Task 2: `.code-flow/theme.css` and the `__THEME_CSS__` token

Theming first, because the bundle scaffold in Task 3 needs the same token and it is cheaper to build it in than to retrofit it.

**Files:**
- Create: `templates/shared/theme.css`
- Modify: `templates/shared/viewer.template.html`, `report.template.html`, `index.template.html`
- Modify: `bin/install.js`, `src/code_flow_skill/cli.py`
- Modify: `tests/test_installer_python.py`, `test/install.test.js`, `tests/test_packaging.py`
- Create: `tests/test_theme.py`

**Interfaces:**
- Consumes: `_SHARED` / `SHARED` from Task 1 — the theme file is a fourth shared path and goes in those lists, so every `EXPECTED_BY_TOOL` row picks it up automatically.
- Produces: the `__THEME_CSS__` token contract, which Task 3's bundle scaffold and Task 4's generator prose both rely on.

- [ ] **Step 1: Write the token contract test first**

Create `tests/test_theme.py`:

```python
"""The theme token, and the file that fills it.

Theming is the one feature in this project with no failure signal: a user's CSS
is inlined verbatim into a generated page, nothing validates it, and a page that
renders wrong looks exactly like a page that renders right until someone opens
it. These tests cover the parts that *are* checkable — that the token exists,
that it sits where later declarations win, and that the shipped file cannot
silently break the light/dark toggle.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

THEMED_SCAFFOLDS = (
    "viewer.template.html",
    "report.template.html",
    "index.template.html",
)


@pytest.mark.parametrize("name", THEMED_SCAFFOLDS)
def test_scaffold_carries_the_theme_token(repo_root: Path, name: str) -> None:
    text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
    assert text.count("__THEME_CSS__") == 1, (
        f"{name} must carry exactly one __THEME_CSS__ token"
    )


@pytest.mark.parametrize("name", THEMED_SCAFFOLDS)
def test_theme_token_comes_after_both_palettes(repo_root: Path, name: str) -> None:
    """The token must sit after the `[data-theme="light"]` block.

    `:root` and `[data-theme="light"]` have equal CSS specificity, so whichever
    is declared last wins. A token placed before the light block would let the
    built-in light palette override the user's colours in light mode only —
    a theme that works until you press the toggle, which is worse than one that
    does not work at all.
    """
    text = (repo_root / "templates" / "shared" / name).read_text(encoding="utf-8")
    root = text.index(":root{")
    light = text.index('[data-theme="light"]{')
    token = text.index("__THEME_CSS__")
    assert root < light < token, (
        f"{name}: __THEME_CSS__ must come after both the :root and "
        f'[data-theme="light"] blocks, so user declarations win in both modes'
    )


def test_shipped_theme_declares_both_palettes(repo_root: Path) -> None:
    """The shipped file must show both blocks, not just `:root`.

    A user who edits a `:root`-only file gets their colours in dark mode and
    their colours in light mode — the toggle appears dead. Shipping both blocks
    pre-filled makes the working shape the default shape.
    """
    css = (repo_root / "templates" / "shared" / "theme.css").read_text(encoding="utf-8")
    assert re.search(r"^:root\s*\{", css, re.MULTILINE), "theme.css has no :root block"
    assert re.search(r'^\[data-theme="light"\]\s*\{', css, re.MULTILINE), (
        "theme.css has no [data-theme=\"light\"] block, so editing it would "
        "break the light/dark toggle"
    )


def test_shipped_theme_is_inert(repo_root: Path) -> None:
    """Every declaration in the shipped file must be commented out.

    The installer overwrites `.code-flow/` templates on every run. If the shipped
    theme carried live declarations, a re-install would be indistinguishable from
    a theme edit, and anyone who had customised their copy would silently lose it
    on upgrade. Shipped inert, the file is a documented menu; the user opts in by
    uncommenting.
    """
    css = (repo_root / "templates" / "shared" / "theme.css").read_text(encoding="utf-8")
    live = [
        line
        for line in css.splitlines()
        if re.match(r"\s*--[a-z-]+\s*:", line) and not line.lstrip().startswith("/*")
    ]
    assert not live, f"theme.css ships live declarations: {live[:3]}"
```

- [ ] **Step 2: Run it and watch every test fail**

Run: `uv run --group dev pytest tests/test_theme.py -v`

Expected: 8 failures — three `__THEME_CSS__` counts of 0, three index lookups raising `ValueError: substring not found`, and two `FileNotFoundError` for the missing `theme.css`.

- [ ] **Step 3: Write `templates/shared/theme.css`**

Every declaration commented out, both blocks present, every custom property the scaffolds define listed at its current default. Derive the list and the values from `templates/shared/viewer.template.html` — read its `:root{}` and `[data-theme="light"]{}` blocks and transcribe them. Do not invent property names or values; the file is a menu of what actually exists.

Head the file with:

```css
/* Code Flow — your theme.
 *
 * Uncomment a line and change its value. Everything here is inlined into every
 * generated page after the built-in styles, so your declarations win.
 *
 * Keep both blocks. `:root` is the dark palette and `[data-theme="light"]` is the
 * light one; they have equal CSS specificity, so setting only `:root` would apply
 * your colours in light mode too and make the theme toggle look broken.
 *
 * This file is overwritten when you re-run the installer. Keep a copy of your
 * edits somewhere else, or version it.
 */
```

That last paragraph is a real caveat and must be in the shipped file: `.code-flow/` templates are overwritten on every install, so a customised `theme.css` is lost on upgrade. Say so where the user will read it rather than only in the README.

- [ ] **Step 4: Add the token to all three scaffolds**

In each of `viewer.template.html`, `report.template.html` and `index.template.html`, insert on its own line immediately after the closing brace of the `[data-theme="light"]{...}` block:

```
__THEME_CSS__
```

It sits inside the existing `<style>` element — do not add a second one. Nothing else in any scaffold changes.

- [ ] **Step 5: Install it**

In `bin/install.js`, add to `sharedFiles`:

```js
  ["theme.css", "your theme"],
```

In `src/code_flow_skill/cli.py`, add to `_SHARED_FILES`:

```python
    ("theme.css", "your theme"),
```

In `tests/test_installer_python.py` add `".code-flow/theme.css"` to `_SHARED`, and in `test/install.test.js` add it to `SHARED`. Every `EXPECTED_BY_TOOL` row picks it up from there — that is why Task 1 composed those lists rather than writing them out per row.

In `tests/test_packaging.py`, add to `EXPECTED_IN_WHEEL`:

```python
    "code_flow_skill/templates/shared/theme.css",
```

- [ ] **Step 6: Run both suites**

```bash
uv run --group dev pytest -q
```

```bash
npm test
```

Expected: green. Python gains 8 from `tests/test_theme.py`; the per-tool rows now expect one more shared file each.

- [ ] **Step 7: Mutation proof, four ways**

1. Move `__THEME_CSS__` in `viewer.template.html` to just before the `[data-theme="light"]` block. Expected: `test_theme_token_comes_after_both_palettes` FAILS for viewer. **This is the one that matters** — it is the difference between a theme that works and one that dies on the toggle, and it is invisible to every other check.
2. Delete the `[data-theme="light"]` block from `templates/shared/theme.css`. Expected: `test_shipped_theme_declares_both_palettes` FAILS.
3. Uncomment one declaration in `theme.css`. Expected: `test_shipped_theme_is_inert` FAILS naming that property.
4. Add a second `__THEME_CSS__` to `index.template.html`. Expected: `test_scaffold_carries_the_theme_token` FAILS on the count. (A doubled token would inline the user's CSS twice — harmless visually, but it means a generator that replaced only the first occurrence would leave a literal `__THEME_CSS__` in the page.)

- [ ] **Step 8: Commit**

```bash
git add templates/shared/theme.css templates/shared/*.template.html bin/install.js src/code_flow_skill/cli.py tests/ test/
git commit -m "feat: ship an editable theme.css and inline it through a __THEME_CSS__ token"
```

---

### Task 3: The bundle scaffold

**Files:**
- Create: `templates/shared/bundle.template.html`
- Modify: `bin/install.js`, `src/code_flow_skill/cli.py`
- Modify: `tests/test_installer_python.py`, `test/install.test.js`, `tests/test_packaging.py`
- Modify: `test/viewer-validation.test.js`

**Interfaces:**
- Consumes: `__THEME_CSS__` from Task 2, and `_SHARED` / `SHARED`.
- Produces: `.code-flow/bundle.template.html` carrying `__BUNDLE_DATA__`, which Task 4's generator prose fills.

- [ ] **Step 1: Write the validator test first**

The three existing scaffolds each mark a pure `validate(raw, TOKEN)` between `/* ==== validate:start ==== */` and `/* ==== validate:end ==== */`, which `test/viewer-validation.test.js` lifts with `new Function` and drives with no DOM. The bundle gets the same treatment.

Append to `test/viewer-validation.test.js`, following the shape the existing scaffold cases use in that file:

```js
const bundleValidate = liftValidator("bundle.template.html");

test("bundle validator rejects the unreplaced token", () => {
  // Written as a concatenation so a naive string replace over this file cannot
  // rewrite the check itself — the same guard the other three scaffolds use.
  const TOKEN = "__BUNDLE" + "_DATA__";
  const r = bundleValidate(TOKEN, TOKEN);
  assert.equal(r.ok, false);
  assert.match(r.error, /not been generated|placeholder/i);
});

test("bundle validator rejects malformed JSON", () => {
  const r = bundleValidate("{not json", "__BUNDLE" + "_DATA__");
  assert.equal(r.ok, false);
});

test("bundle validator requires an index and a flows array", () => {
  const TOKEN = "__BUNDLE" + "_DATA__";
  assert.equal(bundleValidate('{"flows":[]}', TOKEN).ok, false, "missing index");
  assert.equal(bundleValidate('{"index":{}}', TOKEN).ok, false, "missing flows");
});

test("bundle validator accepts a report-less bundle", () => {
  // `report` is optional: a project that has never run /code-flow.quality has
  // no quality-report.json, and that is not an error.
  const TOKEN = "__BUNDLE" + "_DATA__";
  const data = '{"index":{"flows":[]},"flows":[]}';
  assert.equal(bundleValidate(data, TOKEN).ok, true);
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `npm test`

Expected: FAIL — `liftValidator` cannot read `templates/shared/bundle.template.html`.

- [ ] **Step 3: Build the scaffold**

`templates/shared/bundle.template.html` is one self-contained page that does what the three existing scaffolds do between them. Build it by composing them rather than writing new rendering code — the graph rendering, the report rendering and the card listing are all working code that has been through review.

Requirements, all load-bearing:

- **Exactly two tokens**: `__BUNDLE_DATA__` and `__THEME_CSS__`. No `__FLOW_DATA__`, no `__INDEX_DATA__`, no `__REPORT_DATA__` — the bundle carries everything in one object.
- **`__BUNDLE_DATA__` shape**: `{ "index": <the index.json object>, "flows": [<each slug.json object>], "report": <the quality-report.json object, or null> }`.
- **`__THEME_CSS__` after the `[data-theme="light"]` block**, exactly as Task 2 placed it in the other three. `tests/test_theme.py` does not cover this file — add `"bundle.template.html"` to its `THEMED_SCAFFOLDS` tuple so it does.
- **A `validate(raw, TOKEN)` between the two sentinel comments**, pure, no DOM, returning `{ok: true}` or `{ok: false, error: "..."}`. It must reject the unreplaced token, unparseable JSON, and an object missing `index` or `flows`. It must accept a missing or null `report`.
- **Never a blank screen.** On any validation failure the page renders the error card, exactly as the other three do.
- **Landing view is the index.** Opening the file shows the flow listing; selecting a flow shows that flow's graph; the report, when present, is reachable from the landing view. No network, no build step, opens from `file://`.
- **Self-contained.** No external stylesheet, script, font or image.

- [ ] **Step 4: Run the validator tests**

```bash
npm test
```

Expected: the four bundle validator tests pass. If `bundle validator accepts a report-less bundle` fails, the validator is requiring `report` — fix the validator, not the test.

- [ ] **Step 5: Install it**

Add `["bundle.template.html", "bundled viewer"]` to `sharedFiles` in `bin/install.js` and `("bundle.template.html", "bundled viewer")` to `_SHARED_FILES` in `src/code_flow_skill/cli.py`. Add `".code-flow/bundle.template.html"` to `_SHARED` / `SHARED`, and `"code_flow_skill/templates/shared/bundle.template.html"` to `EXPECTED_IN_WHEEL`.

Add `"bundle.template.html"` to `THEMED_SCAFFOLDS` in `tests/test_theme.py`.

- [ ] **Step 6: Run both suites**

```bash
uv run --group dev pytest -q
```

```bash
npm test
```

Expected: green, with two more `tests/test_theme.py` cases (token present, token positioned) and one more shared file in every `EXPECTED_BY_TOOL` row.

- [ ] **Step 7: Mutation proof, three ways**

1. Change the bundle validator to accept the unreplaced token. Expected: `bundle validator rejects the unreplaced token` FAILS.
2. Make the validator require `report`. Expected: `bundle validator accepts a report-less bundle` FAILS. This is the mutation guarding the case a user hits on day one, before they have ever run the quality command.
3. Remove `__THEME_CSS__` from the bundle scaffold. Expected: `test_scaffold_carries_the_theme_token` FAILS for `bundle.template.html`.

- [ ] **Step 8: Render it once, by hand**

No test in this repository renders anything. Build a bundle from this repository's own `Code_Flows/` artifacts, open it in a browser, and confirm the landing view lists the flows, a flow opens its graph, and the report is reachable. Record what you saw in your report.

If `Code_Flows/` here is empty or stale, say so and skip rather than fabricating data — but say so loudly, because it means the scaffold ships unrendered.

- [ ] **Step 9: Commit**

```bash
git add templates/shared/bundle.template.html bin/install.js src/code_flow_skill/cli.py tests/ test/
git commit -m "feat: add the bundled single-file viewer scaffold"
```

---

### Task 4: `--output`, written into every host

This is the parity-tax task. The same two rules — the `--output` flag and the theme inlining — must be stated in six hand-maintained templates and stay in agreement. `tests/test_host_parity.py` catches Claude/Gemini divergence; nothing compares Copilot's wording to either, so Copilot is where drift will hide.

**Files:**
- Modify: `templates/claude/code-flow.map.md`, `templates/claude/code-flow.quality.md`
- Modify: `templates/gemini/code-flow.map.toml`, `templates/gemini/code-flow.quality.toml`
- Modify: `templates/copilot/code-flow.map.prompt.md`, `templates/copilot/code-flow.quality.prompt.md`
- Regenerate: `templates/shared/code-flow-map/SKILL.md`, `templates/shared/code-flow-quality/SKILL.md`
- Modify: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: `__BUNDLE_DATA__` and `__THEME_CSS__` from Tasks 2 and 3.
- Produces: nothing later tasks read.

- [ ] **Step 1: Write the contract tests first**

Append to `tests/test_template_contracts.py`:

```python
@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_documents_the_output_flag(repo_root: Path, host: str, name: str) -> None:
    """`--output` is parsed in step 1 with the other flags, so it must be stated
    there — not only in whatever section describes the bundle.

    Scoped to step 1's own region for the same reason
    `test_map_template_documents_the_mode_flags` is: unscoped, the token would
    be satisfied by the bundle section further down, and deleting the flag from
    the place it is actually read would leave the assertion green.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    region = _section_region(text, _STEP1_START, _STEP1_END)
    assert "files|bundle|both" in region, f"{host}/{name} step 1 never mentions --output"


@pytest.mark.parametrize("host,name", MAP_TEMPLATES + QUALITY_TEMPLATES)
def test_template_always_writes_the_json_artifacts(
    repo_root: Path, host: str, name: str
) -> None:
    """`--output bundle` suppresses pages, never data.

    `/code-flow.quality` reads `index.json`, `inventory.json` and the per-flow
    sidecars; a mode that skipped them would break it silently, and nothing else
    in this repository couples the two commands tightly enough to notice.
    Keyed on the literal clause every host must carry.
    """
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "never suppresses the JSON" in text, (
        f"{host}/{name} does not state that --output never suppresses the JSON artifacts"
    )


@pytest.mark.parametrize("host,name", MAP_TEMPLATES + QUALITY_TEMPLATES)
def test_template_inlines_the_theme(repo_root: Path, host: str, name: str) -> None:
    """Every page-writing step must fill `__THEME_CSS__`, and must not fail when
    `.code-flow/theme.css` is absent — an absent theme is the default state, not
    an error."""
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "__THEME_CSS__" in text, f"{host}/{name} never fills the theme token"
    assert re.search(r"theme\.css.{0,200}(does not exist|is absent|missing)", text, re.S), (
        f"{host}/{name} does not say what to do when theme.css is absent"
    )
```

- [ ] **Step 2: Run them and watch them fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -k "output_flag or json_artifacts or inlines_the_theme" -v`

Expected: 14 failures — 3 hosts × 1 map-only test, plus 6 hosts-and-commands × 2.

- [ ] **Step 3: Write the rules into Claude's map template**

In `templates/claude/code-flow.map.md`, extend step 1's flag-parsing paragraph with:

```
`--output files|bundle|both` chooses which HTML gets written, default `files`. `files` writes `index.html`, one page per flow, and the quality report page, exactly as before. `both` adds `Code_Flows/code-flow.html`, a single self-contained page carrying every flow. `bundle` writes that page and no other HTML. If its value is not one of those three, say what you read, use `files`, and carry on. **`--output` never suppresses the JSON artifacts** — `index.json`, `<functionality_name>.json` and `inventory.json` are written in every mode, because `/code-flow.quality` reads them and a run that skipped them would break it silently.
```

Then add a new step after 6c:

```
**6d. The bundle.** If `--output` is `bundle` or `both`, read `.code-flow/bundle.template.html` and write `Code_Flows/code-flow.html` as an **exact copy** with two tokens replaced. `__BUNDLE_DATA__` becomes `{"index": <the object you just wrote to index.json>, "flows": [<the full JSON object for every flow in the registry, read back from its sidecar>], "report": <the object in Code_Flows/quality-report.json if that file exists and parses, otherwise null>}`. `__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string if that file does not exist or cannot be read — an absent theme is the normal case and is never an error. Inside every string value, replace each `</` with `<\/`, exactly as in step 5a.

Rebuild it from the sidecars every time, never by editing an existing bundle: the JSON is the data and this page is one rendering of it, so a bundle is always current by construction. If a sidecar is missing or does not parse, leave that flow out, and say which and why in your step 7 report.

If `.code-flow/bundle.template.html` does not exist, say so and skip the bundle. There is no fallback page here.
```

And in step 7, add `Code_Flows/code-flow.html` to the reported paths when it was written.

The same theme rule must also reach 5b and 6c, which write the other pages. Add to each: `__THEME_CSS__` becomes the contents of `.code-flow/theme.css`, or an empty string if that file does not exist or cannot be read.

- [ ] **Step 4: Mirror it into Gemini, then Copilot**

Apply the identical text to `templates/gemini/code-flow.map.toml`, respecting the two documented divergences the parity baseline expects: no Claude-only tool names, and plain three-backtick fences inside the TOML `'''` string.

Then write the Copilot equivalent in `templates/copilot/code-flow.map.prompt.md` in its own numbered-list register, and add the theme rule to all three quality templates — they write `quality-report.html` and must fill `__THEME_CSS__` too.

- [ ] **Step 5: Check parity before regenerating**

```bash
uv run --group dev pytest tests/test_host_parity.py -v
```

Expected: `BASELINE_MAP` still 27 and `BASELINE_QUALITY` still 0. **If the map baseline moved, you introduced divergence** — fix the templates, never the constant. The constant is pinned by its own test for exactly this reason.

- [ ] **Step 6: Regenerate both `SKILL.md` bodies**

The skill bodies are derived from the Gemini templates, not hand-edited. Re-run the Step 4 generator from Phase 4's plan (`docs/superpowers/plans/2026-08-15-phase4-agent-skills.md`, Task 2 Step 4) so both `templates/shared/code-flow-*/SKILL.md` pick up the new prose, then confirm `tests/test_skill_templates.py::test_skill_body_is_derived_from_the_gemini_template` passes. Write bytes, not text — `Path.write_text()` translates `\n` to `\r\n` on Windows.

- [ ] **Step 7: Run both suites**

```bash
uv run --group dev pytest -q
```

```bash
npm test
```

Expected: green, including the 14 new contract assertions and the unchanged parity baselines.

- [ ] **Step 8: Mutation proof, three ways**

1. Delete the `--output` sentence from `templates/copilot/code-flow.map.prompt.md` step 1 only. Expected: `test_map_template_documents_the_output_flag` FAILS for copilot alone. This is the drift that has no other guard — Copilot's wording is compared to nothing.
2. Delete the "never suppresses the JSON" clause from `templates/claude/code-flow.quality.md`. Expected: `test_template_always_writes_the_json_artifacts` FAILS for that host.
3. Delete the theme fallback sentence from `templates/gemini/code-flow.map.toml`. Expected: `test_template_inlines_the_theme` FAILS for gemini, and `test_skill_body_is_derived_from_the_gemini_template` FAILS too, since the skill body no longer matches its source.

- [ ] **Step 9: Commit**

```bash
git add templates/ tests/test_template_contracts.py
git commit -m "feat: add --output files|bundle|both and theme inlining to every host"
```

---

### Task 5: Docs, and the version

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
If a row shows only one form, that host reads only one file. Both forms read and
write the same `Code_Flows/` artifacts, so a flow mapped by one is readable by the
other.

**GitHub Copilot is two surfaces.** VS Code Copilot Chat lists the prompt file and
not the skill — Agent Skills there are still an
[experimental feature](https://code.visualstudio.com/docs/agent-customization/agent-skills).
The Copilot CLI lists **both**, so you will see `/code-flow.map` and `/code-flow-map`
side by side: two commands doing the same job, one from each form, not a duplicate.
Observed 2026-08-17 on VS Code 1.132.0 with Copilot Chat 0.35.3, and Copilot CLI 1.0.10.
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

**The Copilot CLI lists both forms**, so `/code-flow.map` and `/code-flow-map` appear
side by side there. They are two commands doing the same job — one from the prompt file,
one from the skill — not a duplicate entry. Either should work; this package installs
both because VS Code Chat has only the first and Codex, Antigravity and Gemini CLI have
only the second.
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

- [ ] **Step 5b: Document `--output` and theming in the README**

The CHANGELOG records these in Step 6, but a user reads the README. Add a `## Output and appearance` section immediately after `## Interactive HTML view`:

```markdown
## Output and appearance

### One file you can send someone

By default `/code-flow.map` writes what it always has: `Code_Flows/index.html`, one page
per flow, and `quality-report.html`. Add `--output both` and it also writes
**`Code_Flows/code-flow.html`** — a single self-contained page carrying the index, every
mapped flow and the quality report. One file, no server, opens from `file://`. Use
`--output bundle` to write that page and no other HTML.

```text
/code-flow.map --output both
```

The bundle is rebuilt from `Code_Flows/`'s JSON artifacts every run, so it is never
stale — and **no `--output` mode ever skips those artifacts**, because `/code-flow.quality`
reads them.

It carries every flow, so it grows with your map. On a large repository that is a large
file, which is why `files` is still the default.

### Your own colours

The installer writes `.code-flow/theme.css` listing every colour the pages use as a CSS
custom property, at its current default, commented out. Uncomment what you want to change:

```css
:root {
  --accent: #7c5cff;
}
[data-theme="light"] {
  --accent: #5b3fd6;
}
```

Your declarations are inlined into every generated page after the built-in styles, so they
win. Leave the file alone and nothing changes.

**Keep both blocks.** `:root` is the dark palette and `[data-theme="light"]` is the light
one, and they have equal CSS specificity — set only `:root` and your colours apply in both
modes, making the theme toggle look broken.

**Re-running the installer overwrites `.code-flow/theme.css`**, along with the other
templates in that directory. Keep your edits in version control or a copy elsewhere.
```

Then, in the `## Files written` table, add the two new shared rows so
`test_readme_files_written_table_lists_exactly_the_installed_set` passes:

```markdown
| _All tools_ | — | `.code-flow/bundle.template.html` (bundled viewer scaffold) |
| _All tools_ | — | `.code-flow/theme.css` (your colours; edit to taste) |
```

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

### Added — output and appearance

- **`--output files|bundle|both` on `/code-flow.map`**, default `files`. `both` adds
  `Code_Flows/code-flow.html`, one self-contained page carrying the index, every mapped
  flow and the quality report — the file to send someone. `bundle` writes that page and
  no other HTML. **No mode suppresses the JSON artifacts**, which `/code-flow.quality`
  reads. The bundle is rebuilt from those artifacts on every run, so it is never stale.
- **`.code-flow/theme.css`** — every colour the pages use, as CSS custom properties at
  their current defaults, commented out. Uncomment and edit; your values are inlined into
  every generated page after the built-in styles. Absent or untouched, nothing changes.
  Keep both the `:root` and `[data-theme="light"]` blocks or the light/dark toggle will
  appear broken, which is why the shipped file has both. **The installer overwrites this
  file**, so version your edits or keep a copy.
- A bundle carries every flow, so it grows with your map. On a large repository it is a
  large file; the loose pages stay small, which is why `files` is still the default.

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

**Then fix the count.** The checklist says "Do this for ALL THREE files" and `SCAFFOLDS` lists three. There are now four — `bundle.template.html` joins them, and it is the one that most needs opening, because it does what all three others do in a single document and nothing in either suite renders it. Add it to `SCAFFOLDS`, change the closing line to say four, and add a line to item 1 telling the maintainer to open a generated bundle and walk it: landing view lists the flows, a flow opens its graph, the report is reachable.

**And add the theme to the same pass.** Uncomment one property in `.code-flow/theme.css`, regenerate any page, and confirm the colour changed in both light and dark. That is the only check that will ever exist for theming — a user's CSS is inlined verbatim and nothing validates it.

Then add these to the checklist test in `test/prepublish-check.test.js`:

```js
  assert.match(r.stdout, /Copilot CLI/i, "checklist does not distinguish the two Copilot surfaces");
  assert.match(r.stdout, /bundle\.template\.html/, "checklist does not name the bundle scaffold");
  assert.match(r.stdout, /theme\.css/, "checklist does not cover a themed render");
  assert.match(r.stdout, /ALL FOUR/i, "checklist still says three scaffolds");
```

Run `npm test`, then mutation-prove each by deleting the clause it names and confirming the matching assertion fails.

- [ ] **Step 10: Commit**

```bash
git add README.md CHANGELOG.md package.json pyproject.toml tests/test_packaging.py scripts/prepublish-check.js test/prepublish-check.test.js
git commit -m "docs: document the two Copilot surfaces and the per-host --tool, and bump to 1.1.0"
```

---

## Before this ships

**Nothing here is release-blocked.** The gate that governed the previous revision of this plan — confirming the skill works on Copilot before deleting the prompt files — was run, and it is what overturned that plan. Nothing is being removed now, so no host can end up with less than it has today.

Three things must happen before publishing `1.1.0`, and two of them are new:

- **The manual browser pass now covers four scaffolds, not three.** `bundle.template.html` is the one to spend time on: it does what all three others do in a single document, and nothing in either suite renders it. Walk a real generated bundle — landing view lists the flows, a flow opens its graph, the report is reachable, the switcher works.
- **Render one themed page.** Uncomment a property in `.code-flow/theme.css`, regenerate, and confirm the colour changed in **both** light and dark. A user's CSS is inlined verbatim and nothing validates it, so this is the only check theming will ever get. Getting this wrong looks like a broken toggle, not like an error.
- **Install into a real project with `--tool claude` and confirm no `.agents/` appears.** It is the one behaviour this phase takes away, and the tests assert it in a temp directory rather than in a project that already has one.
