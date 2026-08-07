# Code Flow 1.0.0 — Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the command surface to `code-flow.map`, eliminate the duplicated template tree, move Copilot to invocable prompt files, and make the map emit machine-readable artifacts — all covered by the repository's first automated tests.

**Architecture:** This repository is an *installer*, not an analyzer. Both CLIs (`bin/install.js` for npm, `src/code_flow_skill/cli.py` for Python) do nothing but copy prompt-template files into a consuming project. All analysis behavior lives in the prompt text of those templates. Therefore "implementation" here means two things: changing which files get copied where (testable mechanically), and changing the instructions inside the templates (testable only as content contracts). Phase 1 delivers no new analysis; it establishes the naming, packaging, and artifact contracts that phases 2 and 3 build on.

**Tech Stack:** Node 24 (`node:test`, built in — no test dependency added), Python 3.12 + pytest, hatchling for Python packaging, uv for builds.

## Global Constraints

- Target version is exactly `1.0.0`, set identically in `package.json` and `pyproject.toml`.
- Command names use dots: `code-flow.map`. If a host rejects a dot, fall back to a dash (`code-flow-map`) — never to host-native directory namespacing (`code-flow:map`).
- Root `templates/` is the single source of truth for all template files. `src/code_flow_skill/templates/` must not exist when phase 1 completes.
- Installers are plain file copies. No read-modify-write, no guard strings, no idempotency logic anywhere in either installer.
- Every path written into a generated artifact uses forward slashes and is repo-relative.
- Both installers must install the identical set of files for a given `--tool` value.
- Windows is the development platform; all commands in this plan are written for Git Bash and must not assume POSIX-only tools beyond what Git Bash provides.
- Do not add runtime dependencies to either package. `pytest` is a dev dependency only; Node uses its built-in test runner.

## File Structure

**Created:**
- `tests/__init__.py` — makes `tests/` a package so pytest resolves imports predictably
- `tests/conftest.py` — repo-root path resolution and the shared `run_python_installer` helper
- `tests/test_installer_python.py` — Python installer file-placement tests
- `tests/test_packaging.py` — wheel contents and version-consistency tests
- `tests/test_template_contracts.py` — assertions about template *content* (tokens, required instructions)
- `test/install.test.js` — Node installer file-placement tests
- `templates/copilot/code-flow.map.prompt.md` — Copilot invocable prompt file (replaces the instructions fragment)
- `docs/superpowers/plans/2026-08-06-phase1-foundation.md` — this plan

**Modified:**
- `pyproject.toml` — version, hatchling `force-include`, pytest dev dependency
- `package.json` — version, `test` script, `files` array
- `bin/install.js` — new template map, Copilot prompt-file copy, remove append logic
- `src/code_flow_skill/cli.py` — same changes, plus a template-resolution fallback for source-tree runs
- `templates/claude/code-flow.md` → `templates/claude/code-flow.map.md` (renamed, then edited)
- `templates/gemini/code-flow.toml` → `templates/gemini/code-flow.map.toml` (renamed, then edited)
- `README.md` — rename, migration notes, Copilot prompt files, manual-install paths

**Deleted:**
- `src/code_flow_skill/templates/` — the entire mirrored tree (4 files)
- `templates/copilot/code-flow.instructions.md` — superseded by the prompt file

**Responsibility boundaries:** `bin/install.js` and `cli.py` each own "put these files there" for one packaging ecosystem and nothing else. Template files own all analysis instructions. Test files are split by what they assert about — installer placement, packaging output, template content — so a failure names its own cause.

---

### Task 1: Establish the test harness

The repository has no tests. This task creates both harnesses and locks in current, correct behavior *before* anything is renamed, so later tasks have a safety net.

**Note on TDD:** These are deliberately *characterization* tests — they describe behavior that already works and must keep working. They pass on first run. That is correct for this task and only this task; every later task writes a failing test first.

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_installer_python.py`
- Create: `test/install.test.js`
- Modify: `pyproject.toml`
- Modify: `package.json`

**Interfaces:**
- Consumes: nothing
- Produces: `tests/conftest.py` exposes two pytest fixtures — `repo_root` (a `pathlib.Path` to the repository root) and `run_python_installer` (a callable `(target: Path, tool: str = "all") -> None` that invokes the installer in-process). Later tasks use both.

- [ ] **Step 1: Create the Python test package marker**

Create `tests/__init__.py` as an empty file:

```python
```

- [ ] **Step 2: Create the shared Python fixtures**

Create `tests/conftest.py`:

```python
"""Shared fixtures for the installer test suite.

The installer is imported in-process rather than shelled out to, so that a
failure surfaces as a Python traceback instead of a non-zero exit code.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def run_python_installer(monkeypatch) -> Callable[..., None]:
    """Return a callable that runs the Python installer against a target dir."""
    from code_flow_skill import cli

    def _run(target: Path, tool: str = "all") -> None:
        monkeypatch.setattr(
            sys, "argv", ["code-flow-skill", "--target", str(target), "--tool", tool]
        )
        cli.main()

    return _run
```

- [ ] **Step 3: Write the Python characterization test**

Create `tests/test_installer_python.py`:

```python
"""Installer file-placement tests for the Python CLI."""
from __future__ import annotations

from pathlib import Path


def test_installs_viewer_scaffold(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path)
    viewer = tmp_path / ".code-flow" / "viewer.template.html"
    assert viewer.is_file()
    assert "__FLOW_DATA__" in viewer.read_text(encoding="utf-8")


def test_tool_selection_installs_only_that_tool(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="gemini")
    assert not (tmp_path / ".claude").exists()
    assert (tmp_path / ".gemini").is_dir()
```

- [ ] **Step 4: Add pytest as a dev dependency**

In `pyproject.toml`, add this block immediately after the `[project.scripts]` block:

```toml
[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 5: Run the Python tests**

Run: `uv run --group dev pytest -v`
Expected: PASS, 2 tests.

- [ ] **Step 6: Write the Node characterization test**

Create `test/install.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const installer = path.join(repoRoot, "bin", "install.js");

export function runInstaller(target, tool = "all") {
  execFileSync(process.execPath, [installer, "--target", target, "--tool", tool], {
    stdio: "pipe",
  });
}

export function tempTarget() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "code-flow-test-"));
}

test("installs the viewer scaffold", () => {
  const target = tempTarget();
  runInstaller(target);
  const viewer = path.join(target, ".code-flow", "viewer.template.html");
  assert.ok(fs.existsSync(viewer));
  assert.match(fs.readFileSync(viewer, "utf8"), /__FLOW_DATA__/);
});

test("tool selection installs only that tool", () => {
  const target = tempTarget();
  runInstaller(target, "gemini");
  assert.ok(!fs.existsSync(path.join(target, ".claude")));
  assert.ok(fs.existsSync(path.join(target, ".gemini")));
});
```

- [ ] **Step 7: Add the Node test script**

In `package.json`, replace the `scripts` block with:

```json
  "scripts": {
    "check": "node bin/install.js --help",
    "test": "node --test test/",
    "postinstall": "node bin/postinstall.js"
  },
```

- [ ] **Step 8: Run the Node tests**

Run: `npm test`
Expected: PASS, 2 tests.

- [ ] **Step 9: Commit**

```bash
git add tests test package.json pyproject.toml
git commit -m "test: add installer test harness for npm and Python"
```

---

### Task 2: Remove the duplicated template tree

`templates/` and `src/code_flow_skill/templates/` currently hold byte-identical copies. This task makes root `templates/` the single source.

**Critical detail:** after deleting the mirror, `importlib.resources.files("code_flow_skill")` resolves to `src/code_flow_skill/`, which no longer contains `templates/`. The installer would break when run from the source tree — which is exactly how the tests run it. `cli.py` therefore needs a resolution fallback: packaged location first, repository root second.

**Files:**
- Modify: `src/code_flow_skill/cli.py:9-11`
- Modify: `pyproject.toml`
- Create: `tests/test_packaging.py`
- Delete: `src/code_flow_skill/templates/` (4 files)

**Interfaces:**
- Consumes: `repo_root` and `run_python_installer` fixtures from Task 1.
- Produces: `cli._template_root() -> Path`, returning the directory that contains `claude/`, `gemini/`, `copilot/`, and `shared/`. Task 3 and Task 4 both call `_read_template` which is built on it.

- [ ] **Step 1: Write the failing packaging test**

Create `tests/test_packaging.py`:

```python
"""Tests that the built wheel actually carries the template files."""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

EXPECTED_IN_WHEEL = "code_flow_skill/templates/shared/viewer.template.html"


def test_wheel_contains_templates(tmp_path: Path, repo_root: Path) -> None:
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=repo_root,
        check=True,
        capture_output=True,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
    assert EXPECTED_IN_WHEEL in names


def test_source_mirror_is_gone(repo_root: Path) -> None:
    assert not (repo_root / "src" / "code_flow_skill" / "templates").exists()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --group dev pytest tests/test_packaging.py -v`
Expected: `test_source_mirror_is_gone` FAILS (the mirror still exists). `test_wheel_contains_templates` may pass, since the mirror is currently packaged — that is the behavior being replaced.

- [ ] **Step 3: Add force-include to the build config**

In `pyproject.toml`, replace the `[tool.hatch.build.targets.wheel]` block with:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/code_flow_skill"]

[tool.hatch.build.targets.wheel.force-include]
"templates" = "code_flow_skill/templates"

[tool.hatch.build.targets.sdist]
include = ["src", "templates", "README.md", "LICENSE", "NOTICE", "pyproject.toml"]
```

- [ ] **Step 4: Delete the mirrored tree**

```bash
git rm -r src/code_flow_skill/templates
```

- [ ] **Step 5: Add the template-resolution fallback**

In `src/code_flow_skill/cli.py`, replace lines 9-11 (the `_read_template` function) with:

```python
def _template_root() -> Path:
    """Return the directory holding the template trees.

    Prefers the packaged location (``code_flow_skill/templates``, placed there
    by hatchling force-include). Falls back to the repository's root
    ``templates/`` directory so the installer also works when run directly
    from a source checkout, where the packaged copy does not exist.
    """
    packaged = Path(str(files("code_flow_skill").joinpath("templates")))
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "templates"


def _read_template(*parts: str) -> str:
    return _template_root().joinpath(*parts).read_text(encoding="utf-8")
```

- [ ] **Step 6: Run the packaging tests**

Run: `uv run --group dev pytest tests/test_packaging.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 7: Run the whole suite to prove nothing regressed**

Run: `uv run --group dev pytest -v && npm test`
Expected: PASS, 4 Python tests and 2 Node tests.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "build: make root templates/ the single source, drop the src mirror"
```

---

### Task 3: Rename to code-flow.map

**Files:**
- Rename: `templates/claude/code-flow.md` → `templates/claude/code-flow.map.md`
- Rename: `templates/gemini/code-flow.toml` → `templates/gemini/code-flow.map.toml`
- Modify: `bin/install.js:37-46`
- Modify: `src/code_flow_skill/cli.py:14-25`
- Modify: `tests/test_installer_python.py`
- Modify: `test/install.test.js`

**Interfaces:**
- Consumes: `cli._read_template` from Task 2; `runInstaller`/`tempTarget` exported from `test/install.test.js` in Task 1.
- Produces: installed command files at `.claude/commands/code-flow.map.md` and `.gemini/commands/code-flow.map.toml`. Task 5 edits the contents of the renamed template files.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_installer_python.py`:

```python
def test_installs_claude_map_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="claude")
    assert (tmp_path / ".claude" / "commands" / "code-flow.map.md").is_file()
    assert not (tmp_path / ".claude" / "commands" / "code-flow.md").exists()


def test_installs_gemini_map_command(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="gemini")
    assert (tmp_path / ".gemini" / "commands" / "code-flow.map.toml").is_file()
    assert not (tmp_path / ".gemini" / "commands" / "code-flow.toml").exists()
```

Append to `test/install.test.js`:

```js
test("installs the claude map command under its dotted name", () => {
  const target = tempTarget();
  runInstaller(target, "claude");
  const commands = path.join(target, ".claude", "commands");
  assert.ok(fs.existsSync(path.join(commands, "code-flow.map.md")));
  assert.ok(!fs.existsSync(path.join(commands, "code-flow.md")));
});

test("installs the gemini map command under its dotted name", () => {
  const target = tempTarget();
  runInstaller(target, "gemini");
  const commands = path.join(target, ".gemini", "commands");
  assert.ok(fs.existsSync(path.join(commands, "code-flow.map.toml")));
  assert.ok(!fs.existsSync(path.join(commands, "code-flow.toml")));
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --group dev pytest -v && npm test`
Expected: 4 new tests FAIL — the installers still write `code-flow.md` / `code-flow.toml`.

- [ ] **Step 3: Rename the template files**

```bash
git mv templates/claude/code-flow.md templates/claude/code-flow.map.md
git mv templates/gemini/code-flow.toml templates/gemini/code-flow.map.toml
```

- [ ] **Step 4: Update the Python installer**

In `src/code_flow_skill/cli.py`, replace the `_install_claude` and `_install_gemini` functions with:

```python
def _install_claude(target: Path) -> None:
    out = target / ".claude" / "commands" / "code-flow.map.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_read_template("claude", "code-flow.map.md"), encoding="utf-8")
    print(f"Installed Claude template: {out}")


def _install_gemini(target: Path) -> None:
    out = target / ".gemini" / "commands" / "code-flow.map.toml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_read_template("gemini", "code-flow.map.toml"), encoding="utf-8")
    print(f"Installed Gemini template: {out}")
```

- [ ] **Step 5: Update the Node installer**

In `bin/install.js`, replace the `toolMap` object with:

```js
const toolMap = {
  claude: {
    src: path.join(pkgRoot, "templates", "claude", "code-flow.map.md"),
    dst: path.join(target, ".claude", "commands", "code-flow.map.md"),
  },
  gemini: {
    src: path.join(pkgRoot, "templates", "gemini", "code-flow.map.toml"),
    dst: path.join(target, ".gemini", "commands", "code-flow.map.toml"),
  },
};
```

- [ ] **Step 6: Run the tests**

Run: `uv run --group dev pytest -v && npm test`
Expected: PASS, 6 Python tests and 4 Node tests.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat!: rename the flow command to code-flow.map"
```

---

### Task 4: Move Copilot to an invocable prompt file

Copilot stops receiving appended prose and gains a real command. This deletes the only read-modify-write path in either installer.

**Open item:** the `.github/prompts/<name>.prompt.md` convention is taken from GitHub Spec Kit and was not verifiable against a local install. Confirm the file is invocable in Copilot Chat during Step 8. If a dot in the filename is rejected, rename to `code-flow-map.prompt.md` and record the divergence in the README — do not change the Claude or Gemini names.

**Files:**
- Create: `templates/copilot/code-flow.map.prompt.md`
- Delete: `templates/copilot/code-flow.instructions.md`
- Modify: `bin/install.js:54-68`
- Modify: `src/code_flow_skill/cli.py:40-50`
- Modify: `tests/test_installer_python.py`
- Modify: `test/install.test.js`

**Interfaces:**
- Consumes: `cli._read_template` from Task 2.
- Produces: `cli._install_copilot(target: Path) -> None` becomes a plain copy with the same signature it has today. Nothing downstream depends on the removed append behavior.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_installer_python.py`:

```python
def test_installs_copilot_prompt_file(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path, tool="copilot")
    assert (tmp_path / ".github" / "prompts" / "code-flow.map.prompt.md").is_file()


def test_copilot_install_does_not_touch_instructions_file(
    tmp_path: Path, run_python_installer
) -> None:
    instructions = tmp_path / ".github" / "copilot-instructions.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# My own notes\n", encoding="utf-8")

    run_python_installer(tmp_path, tool="copilot")

    assert instructions.read_text(encoding="utf-8") == "# My own notes\n"


def test_install_is_repeatable(tmp_path: Path, run_python_installer) -> None:
    run_python_installer(tmp_path)
    first = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    run_python_installer(tmp_path)
    second = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    assert first == second
```

Append to `test/install.test.js`:

```js
test("installs the copilot prompt file", () => {
  const target = tempTarget();
  runInstaller(target, "copilot");
  const prompt = path.join(target, ".github", "prompts", "code-flow.map.prompt.md");
  assert.ok(fs.existsSync(prompt));
});

test("copilot install leaves copilot-instructions.md untouched", () => {
  const target = tempTarget();
  const instructions = path.join(target, ".github", "copilot-instructions.md");
  fs.mkdirSync(path.dirname(instructions), { recursive: true });
  fs.writeFileSync(instructions, "# My own notes\n", "utf8");

  runInstaller(target, "copilot");

  assert.equal(fs.readFileSync(instructions, "utf8"), "# My own notes\n");
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --group dev pytest -v && npm test`
Expected: 5 new tests FAIL — no prompt file is written, and the installers still append to `copilot-instructions.md`.

- [ ] **Step 3: Create the Copilot prompt file**

Create `templates/copilot/code-flow.map.prompt.md`. Take the body of the existing `templates/copilot/code-flow.instructions.md` and place it under this frontmatter, dropping the old `## Code Flow — Documentation Generator` heading and the `### Using Code Flow` heading, since a prompt file is invoked directly rather than read ambiently:

```markdown
---
mode: agent
description: Map a code flow (or the whole codebase) into markdown plus an interactive HTML page.
---

Analyze the codebase and generate flow documentation for the requested functionality.

The user's request follows this prompt. If it is empty, analyze the project structure, suggest 3-5 key flows, and ask which to document.

1. **Identify the target flow** from the user's request. Derive a snake_case filename.
2. **Discover relevant files and functions** — search by file patterns and grep for keywords, then trace the call chain.
3. **Document undocumented functions** — add docstrings to any function in the flow that lacks one.
4. **Generate `Code_Flows/<functionality_name>.md`** containing: a flow description, a MermaidJS diagram in which every function appears as a named node, a bullet list of every function in the diagram, and a reference table with each function's description and its exact `file:line` location.
5. **Generate `Code_Flows/<functionality_name>.html`** by reading `.code-flow/viewer.template.html` and replacing the single token `__FLOW_DATA__` with the flow-data JSON object. Change nothing else in the template. If that file is missing, write a minimal Mermaid-based page instead and tell the user to reinstall `code-flow` for the full viewer.
6. **Report both output paths** to the user.
```

- [ ] **Step 4: Delete the superseded instructions template**

```bash
git rm templates/copilot/code-flow.instructions.md
```

- [ ] **Step 5: Replace the Python Copilot installer**

In `src/code_flow_skill/cli.py`, replace the entire `_install_copilot` function with:

```python
def _install_copilot(target: Path) -> None:
    out = target / ".github" / "prompts" / "code-flow.map.prompt.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        _read_template("copilot", "code-flow.map.prompt.md"), encoding="utf-8"
    )
    print(f"Installed Copilot prompt: {out}")
```

- [ ] **Step 6: Replace the Node Copilot branch**

In `bin/install.js`, delete the entire `if (name === "copilot") { ... continue; }` block and add `copilot` to `toolMap` instead, so all three hosts flow through the same copy path:

```js
const toolMap = {
  claude: {
    src: path.join(pkgRoot, "templates", "claude", "code-flow.map.md"),
    dst: path.join(target, ".claude", "commands", "code-flow.map.md"),
  },
  gemini: {
    src: path.join(pkgRoot, "templates", "gemini", "code-flow.map.toml"),
    dst: path.join(target, ".gemini", "commands", "code-flow.map.toml"),
  },
  copilot: {
    src: path.join(pkgRoot, "templates", "copilot", "code-flow.map.prompt.md"),
    dst: path.join(target, ".github", "prompts", "code-flow.map.prompt.md"),
  },
};
```

The `fs.readFileSync` import usage for the snippet disappears with the deleted block; leave the `import fs` statement, which is still used for `mkdirSync`/`copyFileSync`.

- [ ] **Step 7: Run the tests**

Run: `uv run --group dev pytest -v && npm test`
Expected: PASS, 9 Python tests and 6 Node tests.

- [ ] **Step 8: Manually confirm the Copilot convention**

Install into a scratch directory and open it in an editor with Copilot Chat available:

```bash
node bin/install.js --tool copilot --target /c/Users/ajple/AppData/Local/Temp/claude/copilot-check
```

Confirm `/code-flow.map` appears as an invocable prompt. If the dotted name is rejected, rename the template and both installer paths to `code-flow-map.prompt.md` and note the divergence for the README in Task 6.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat!: install Copilot as an invocable prompt file, drop the append path"
```

---

### Task 5: Emit the JSON sidecar and index

The map command must now leave machine-readable artifacts behind, because phase 3's quality command reads them rather than parsing the generated HTML. This task changes template *instructions* only; there is no executable code to test, so the tests assert content contracts.

**Files:**
- Modify: `templates/claude/code-flow.map.md` (the "Finalize" section)
- Modify: `templates/gemini/code-flow.map.toml` (the equivalent closing section)
- Modify: `templates/copilot/code-flow.map.prompt.md` (step 6)
- Create: `tests/test_template_contracts.py`

**Interfaces:**
- Consumes: the renamed template files from Task 3 and the prompt file from Task 4.
- Produces: the artifact contract that phase 2 extends and phase 3 consumes — `Code_Flows/<slug>.json` holding the flow object, and `Code_Flows/index.json` holding `meta`, `coverage`, and `flows`.

- [ ] **Step 1: Write the failing contract tests**

Create `tests/test_template_contracts.py`:

```python
"""Assertions about template content.

Templates are prompt text, not code, so these tests check that the
instructions a template gives still mention the artifacts it is required to
produce. They catch silent drift between the spec and the prompts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

MAP_TEMPLATES = (
    ("claude", "code-flow.map.md"),
    ("gemini", "code-flow.map.toml"),
    ("copilot", "code-flow.map.prompt.md"),
)


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_json_sidecar(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "<functionality_name>.json" in text


@pytest.mark.parametrize("host,name", MAP_TEMPLATES)
def test_map_template_requires_index(repo_root: Path, host: str, name: str) -> None:
    text = (repo_root / "templates" / host / name).read_text(encoding="utf-8")
    assert "index.json" in text


def test_viewer_scaffold_has_exactly_one_token(repo_root: Path) -> None:
    text = (repo_root / "templates" / "shared" / "viewer.template.html").read_text(
        encoding="utf-8"
    )
    assert text.count("__FLOW_DATA__") == 1
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`
Expected: 6 of 7 FAIL — no map template mentions the sidecar or the index yet. `test_viewer_scaffold_has_exactly_one_token` passes.

- [ ] **Step 3: Update the Claude template**

In `templates/claude/code-flow.map.md`, replace the entire `#### 6. Finalize` section with:

````markdown
#### 6. Write the Machine-Readable Artifacts

These files are the contract consumed by `code-flow.quality`. They are not
optional, and they are not derived by parsing the generated HTML.

**6a. The flow sidecar.** Write `Code_Flows/<functionality_name>.json` containing
exactly the JSON object you built in step 5a — the same `meta`, `nodes`, and
`edges`. This is the same data embedded in the HTML page, written as a plain file
so downstream tools never have to parse markup.

**6b. The index.** Create or update `Code_Flows/index.json`. If it does not exist,
create it with this shape. If it does exist, read it, add or replace the entry for
this flow in `flows` (matching on `slug`), and write it back — preserving every
other entry and any existing `coverage` values you did not compute.

```json
{
  "meta": { "root": "<absolute project root, forward slashes>",
            "generated": "<today, YYYY-MM-DD>", "mode": "feature", "schema": 1 },
  "coverage": { "flowsTraced": 1 },
  "flows": [
    { "slug": "user_login", "title": "User Login", "file": "user_login.json",
      "entry": "login_view", "nodes": 9 }
  ]
}
```

- `slug` is the snake_case functionality name; `file` is the sidecar's filename.
- `entry` is the `id` of the node whose `kind` is `entry`.
- `nodes` is the count of entries in the flow's `nodes` array.
- `coverage.flowsTraced` is the length of `flows` after your update.
- Set `meta.mode` to `feature`. Whole-codebase mapping sets it differently and is
  not part of this command yet.

#### 7. Finalize

- Create the `Code_Flows/` directory if it doesn't exist
- Write `Code_Flows/<functionality_name>.md`, `.html`, and `.json`, plus `index.json`
- Report the markdown and HTML paths to the user, and mention that the JSON
  artifacts were updated
````

- [ ] **Step 4: Update the Gemini template**

`templates/gemini/code-flow.map.toml` ends with a `#### 6. Finalize` section whose
text is byte-identical to the one Claude had before Step 3. Replace it with the
identical replacement — same headings, same JSON, same wording — so the two hosts
cannot drift.

The TOML `prompt` value is wrapped in `'''` delimiters. Keep the replacement
inside them, and do not introduce a `'''` sequence anywhere in the body. The
final `'''` on the last line of the file must remain.

Replace this block:

```markdown
#### 6. Finalize

- Create the `Code_Flows/` directory if it doesn't exist
- Write both `Code_Flows/<functionality_name>.md` and `Code_Flows/<functionality_name>.html`
- Report **both** output file paths to the user
```

with this block:

````markdown
#### 6. Write the Machine-Readable Artifacts

These files are the contract consumed by `code-flow.quality`. They are not
optional, and they are not derived by parsing the generated HTML.

**6a. The flow sidecar.** Write `Code_Flows/<functionality_name>.json` containing
exactly the JSON object you built in step 5a — the same `meta`, `nodes`, and
`edges`. This is the same data embedded in the HTML page, written as a plain file
so downstream tools never have to parse markup.

**6b. The index.** Create or update `Code_Flows/index.json`. If it does not exist,
create it with this shape. If it does exist, read it, add or replace the entry for
this flow in `flows` (matching on `slug`), and write it back — preserving every
other entry and any existing `coverage` values you did not compute.

```json
{
  "meta": { "root": "<absolute project root, forward slashes>",
            "generated": "<today, YYYY-MM-DD>", "mode": "feature", "schema": 1 },
  "coverage": { "flowsTraced": 1 },
  "flows": [
    { "slug": "user_login", "title": "User Login", "file": "user_login.json",
      "entry": "login_view", "nodes": 9 }
  ]
}
```

- `slug` is the snake_case functionality name; `file` is the sidecar's filename.
- `entry` is the `id` of the node whose `kind` is `entry`.
- `nodes` is the count of entries in the flow's `nodes` array.
- `coverage.flowsTraced` is the length of `flows` after your update.
- Set `meta.mode` to `feature`. Whole-codebase mapping sets it differently and is
  not part of this command yet.

#### 7. Finalize

- Create the `Code_Flows/` directory if it doesn't exist
- Write `Code_Flows/<functionality_name>.md`, `.html`, and `.json`, plus `index.json`
- Report the markdown and HTML paths to the user, and mention that the JSON
  artifacts were updated
````

- [ ] **Step 5: Update the Copilot prompt file**

In `templates/copilot/code-flow.map.prompt.md`, replace numbered item 6 with:

```markdown
6. **Write the machine-readable artifacts.** Write `Code_Flows/<functionality_name>.json` containing exactly the flow-data JSON object used in step 5. Then create or update `Code_Flows/index.json`, adding or replacing this flow's entry in its `flows` array (matched on `slug`) while preserving all other entries. Each entry holds `slug`, `title`, `file`, `entry`, and `nodes`; the file also carries `meta` (`root`, `generated`, `mode: "feature"`, `schema: 1`) and `coverage.flowsTraced`.
7. **Report both output paths** to the user, and mention that the JSON artifacts were updated.
```

- [ ] **Step 6: Run the contract tests**

Run: `uv run --group dev pytest tests/test_template_contracts.py -v`
Expected: PASS, 7 tests.

- [ ] **Step 7: Run the whole suite**

Run: `uv run --group dev pytest -v && npm test`
Expected: PASS, 16 Python tests and 6 Node tests.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: emit flow JSON sidecar and Code_Flows/index.json"
```

---

### Task 6: Version 1.0.0 and documentation

**Files:**
- Modify: `package.json`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: nothing consumed by later tasks; this is the phase's release gate.

- [ ] **Step 1: Write the failing version test**

In `tests/test_packaging.py`, add `import json` and `import re` to the existing
import block at the top of the file, then append this test at the end:

```python
def test_package_versions_match_and_are_1_0_0(repo_root: Path) -> None:
    npm_version = json.loads((repo_root / "package.json").read_text(encoding="utf-8"))["version"]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match is not None, "no version found in pyproject.toml"
    assert npm_version == match.group(1) == "1.0.0"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --group dev pytest tests/test_packaging.py -v`
Expected: FAIL — both files still read `0.2.0`.

- [ ] **Step 3: Bump both versions**

Set `"version": "1.0.0"` in `package.json` and `version = "1.0.0"` in `pyproject.toml`.

- [ ] **Step 4: Run the test**

Run: `uv run --group dev pytest tests/test_packaging.py -v`
Expected: PASS.

- [ ] **Step 5: Update the README**

Make these edits:

1. **Add a migration section** directly beneath the main heading:

```markdown
## Upgrading from 0.x to 1.0

The command was renamed and the Copilot integration changed. After upgrading:

- `/code-flow` is now `/code-flow.map`. Delete the stale command file:
  `.claude/commands/code-flow.md` or `.gemini/commands/code-flow.toml`.
- Copilot now installs an invocable prompt at
  `.github/prompts/code-flow.map.prompt.md`. The installer no longer edits
  `.github/copilot-instructions.md`, so **remove the old
  `## Code Flow — Documentation Generator` section from that file by hand** —
  otherwise it lingers and contradicts the new prompt.
- `/code-flow.map` now also writes `Code_Flows/<name>.json` and
  `Code_Flows/index.json`. Flows mapped before 1.0 have no sidecar until re-mapped.
```

2. **Update every `/code-flow` usage reference** to `/code-flow.map`.

3. **Update the manual-install copy commands** to the new paths:

```bash
# Claude Code
mkdir -p .claude/commands
cp /path/to/code-flow-skill/templates/claude/code-flow.map.md .claude/commands/code-flow.map.md

# Gemini CLI
mkdir -p .gemini/commands
cp /path/to/code-flow-skill/templates/gemini/code-flow.map.toml .gemini/commands/code-flow.map.toml

# GitHub Copilot
mkdir -p .github/prompts
cp /path/to/code-flow-skill/templates/copilot/code-flow.map.prompt.md .github/prompts/code-flow.map.prompt.md

# Interactive HTML viewer scaffold (needed for all tools)
mkdir -p .code-flow
cp /path/to/code-flow-skill/templates/shared/viewer.template.html .code-flow/viewer.template.html
```

4. **Update the installed-files table** so the Copilot row reads
   `.github/prompts/code-flow.map.prompt.md`, and delete the sentence stating that
   the Copilot installer is idempotent by appending — it is now a plain copy.

5. **Add the artifacts to the output description**: each run writes `.md`, `.html`,
   and `.json` into `Code_Flows/`, plus a shared `index.json`.

6. If Task 4 Step 8 found that Copilot rejects a dotted filename, record the
   `code-flow-map.prompt.md` divergence here.

- [ ] **Step 6: Run the whole suite**

Run: `uv run --group dev pytest -v && npm test`
Expected: PASS, 17 Python tests and 6 Node tests.

- [ ] **Step 7: Verify a clean end-to-end install**

```bash
rm -rf /c/Users/ajple/AppData/Local/Temp/claude/e2e && mkdir -p /c/Users/ajple/AppData/Local/Temp/claude/e2e
node bin/install.js --tool all --target /c/Users/ajple/AppData/Local/Temp/claude/e2e
find /c/Users/ajple/AppData/Local/Temp/claude/e2e -type f | sort
```

Expected exactly four files:

```
.claude/commands/code-flow.map.md
.code-flow/viewer.template.html
.gemini/commands/code-flow.map.toml
.github/prompts/code-flow.map.prompt.md
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "release: 1.0.0 — code-flow.map, prompt-file Copilot, JSON artifacts"
```

---

## Phase 1 Definition of Done

- Both installers place the same four files, verified by tests in both ecosystems.
- `src/code_flow_skill/templates/` no longer exists, and the built wheel still carries the templates.
- No read-modify-write logic remains in either installer.
- `/code-flow.map` instructs writing `<slug>.json` and `index.json` on all three hosts.
- Versions read `1.0.0` in both manifests.
- README documents the rename, the Copilot change, and the manual-upgrade steps.

## Deferred to Later Phases

- `--whole-code-base`, `--detail`, `inventory.json`, file hashes, test roles, idempotent re-runs — phase 2.
- `code-flow.quality`, the four detectors, `--read-code`, `report.template.html`, both report outputs — phase 3.
- `code-flow.violations` — design not started.
- Publishing to npm and PyPI — the operator runs those with their own credentials.
- **Viewer self-validation tests** (feed malformed JSON, assert the error card
  renders instead of a blank page). The spec lists these under Testing, and the
  viewer they target already exists — they are deferred deliberately, not
  overlooked. Asserting on rendered DOM requires either a headless browser or a
  jsdom dev dependency, which is disproportionate for one scaffold. Phase 3 adds
  `report.template.html`, making it two scaffolds and worth the harness; these
  tests land there and cover both.
