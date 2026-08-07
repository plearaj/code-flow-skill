# Code Flow Skill

## Upgrading from 0.x to 1.0

The command was renamed and the Copilot integration changed. After upgrading:

- `/code-flow` is now `/code-flow.map`. Delete the stale command file:
  `.claude/commands/code-flow.md` or `.gemini/commands/code-flow.toml`.
- Copilot now installs an invocable prompt at
  `.github/prompts/code-flow.map.prompt.md`. The installer no longer edits
  `.github/copilot-instructions.md`.
  - **If you use Copilot in VS Code**, remove the old
    `## Code Flow — Documentation Generator` section from
    `.github/copilot-instructions.md` by hand — otherwise it lingers and
    contradicts the new prompt.
  - **If you use Copilot anywhere else** (github.com, JetBrains, Visual Studio,
    the CLI), **keep** that section. Prompt files are a VS Code feature; outside
    VS Code the instructions file is what your Copilot actually reads, and
    deleting it would leave you with no Code Flow skill at all. See the
    **GitHub Copilot** notes under *Usage* below.
- `/code-flow.map` now also writes `Code_Flows/<feature_name>.json` and
  `Code_Flows/index.json`. Flows mapped before 1.0 have no sidecar until re-mapped.

A portable **Code Flow** skill for AI coding assistants — Claude Code, Gemini CLI, and GitHub Copilot. Installs a `/code-flow.map` command that asks the assistant to trace a feature through your codebase and produce **both** a markdown document and an interactive HTML page describing exactly how it works.

## What the skill does

Given a feature or flow name (e.g. `user login`, `password reset`, `checkout`), the assistant will:

1. **Discover** the relevant files and functions using glob + grep searches.
2. **Trace the call chain** from entry point to final output, following every function that participates in the flow.
3. **Docstring any undocumented functions** encountered along the way, editing them in place.
4. **Generate `Code_Flows/<feature_name>.md`** containing:
   - A plain-language description of the flow's purpose and trigger conditions.
   - A MermaidJS flow/sequence diagram with every participating function as a named node.
   - A bullet list of all functions in the diagram.
   - A reference table with each function's description and exact `file:line` location.
5. **Generate `Code_Flows/<feature_name>.html`** — an interactive, self-contained view of the same flow (see below).
6. **Write `Code_Flows/<feature_name>.json`** — the same flow data as plain JSON — and create or update the shared `Code_Flows/index.json` registry with an entry for this flow.
7. **Report** the paths to the generated files.

If you invoke the skill with no argument, the assistant will survey the project and suggest 3–5 candidate flows to pick from.

## Interactive HTML view

Alongside the markdown, the assistant produces a **single self-contained HTML file** you can explore in a browser — no server, no build step, no internet required. Just double-click it. It renders the flow as a browsable graph where you can:

- **Pan/zoom** the layered call graph and **Fit** it to view.
- **Click any function node** to open a side panel with its description, `file:line`, a code snippet, an "Open in VS Code" link, and clickable **Called by** / **Calls** lists to walk the flow.
- **Search/filter** functions by name, file, or description.
- **Highlight a path** — selecting a node lights up its full ancestor and descendant chain, answering "how did execution get here?" and "what happens next?".
- Toggle **light/dark** theme (persisted).

Node colors distinguish `entry` points, ordinary `step`s, `external` (third-party) boundaries, and `io` (DB/network/file) side effects. Edges distinguish plain `call`s, `async` calls (dashed), `conditional` branches (labeled), and `back`/cycle edges.

**How it works:** the installer drops a viewer scaffold at `.code-flow/viewer.template.html`. When you run the command, the assistant only has to emit a small JSON data block and inject it into that scaffold — so the interactive page is produced reliably, and the page self-validates (showing a clear error card, never a blank screen, if the data is malformed). If the scaffold is missing, the assistant falls back to a minimal Mermaid-based page.

## Usage

After installing (see below), invoke from inside your project:

**Claude Code**

```text
/code-flow.map user login
```

**Gemini CLI**

```text
/code-flow.map password reset
```

**GitHub Copilot**

The installer writes an invocable prompt file to `.github/prompts/code-flow.map.prompt.md`.

Prompt files — `.github/prompts/*.prompt.md` with `mode: agent` frontmatter, which is what this one is — are a **VS Code** Copilot Chat feature. In VS Code, open Copilot Chat and select the prompt from the Prompts picker, or try:

```text
/code-flow.map user login
```

Two things this project has **not** verified and therefore does not claim: that Copilot Chat exposes a *dotted* filename as a `/`-command (the `code-flow.map` name follows the [GitHub Spec Kit](https://github.com/github/spec-kit) prompt-file naming convention rather than any confirmed Copilot behavior), and whether Copilot surfaces other than VS Code read prompt files at all. If the slash form doesn't appear, use the Prompts picker.

**If you don't use Copilot in VS Code**, assume the prompt file does nothing for you. Instead, paste the body of `templates/copilot/code-flow.map.prompt.md` — everything below the `---` frontmatter — into `.github/copilot-instructions.md` under a `## Code Flow` heading; that file is read across Copilot surfaces. Upgrading from 0.x, you already have such a section: **keep it** instead of deleting it.

In all three, the assistant writes its output to `Code_Flows/<feature_name>.md`, `Code_Flows/<feature_name>.html`, and `Code_Flows/<feature_name>.json` at the project root, and creates or updates the shared `Code_Flows/index.json` registry.

### Example output

`Code_Flows/user_login.md` will look roughly like:

````markdown
# User Login — Flow

Brief description of what the flow does and when it runs.

## Diagram

```mermaid
flowchart TD
    A[handle_login] --> B[validate_credentials]
    B --> C[create_session]
    C --> D[issue_token]
```

## Functions

- `handle_login`
- `validate_credentials`
- `create_session`
- `issue_token`

## Reference

| Function | Description | File |
|----------|-------------|------|
| `handle_login` | HTTP handler for POST /login | `src/auth/login.py:42` |
| `validate_credentials` | Verifies email + password against the user store | `src/auth/credentials.py:18` |
| ...
````

A sibling `Code_Flows/user_login.html` is written at the same time — the interactive version of the same flow, ready to open in any browser. A `Code_Flows/user_login.json` sidecar (the same flow data as plain JSON) is written alongside it, and `Code_Flows/index.json` is created or updated to register the flow.

## Install

### npm — local project (auto-installs templates)

```bash
npm i @htst/code-flow-skill
```

The `postinstall` script copies the Claude, Gemini, and Copilot templates into your project.

Skip the auto-install with either:

```bash
npm i @htst/code-flow-skill --code_flow_skip_install=true
# or
CODE_FLOW_SKIP_INSTALL=1 npm i @htst/code-flow-skill
```

### npm — global (manual install)

```bash
npm i -g @htst/code-flow-skill
code-flow-skill --tool all --target .
```

### uvx (Python)

```bash
uvx htst-code-flow-skill --tool all --target .
```

### Manual install (no npm, no uvx)

If neither `npm` nor `uvx` is available, you only need to copy two or three small text files into your project. There is no code to build and no runtime dependency.

**1. Get the templates.** Pick whichever is easiest:

- **Download a release (recommended).** Grab `code-flow-templates-*.zip` from the [latest release](https://github.com/plearaj/code-flow-skill/releases/latest) — it contains only the `templates/` directory, nothing else. Unzip it anywhere.
- **Clone or download the repo:**

  ```bash
  git clone https://github.com/plearaj/code-flow-skill.git
  # or: download https://github.com/plearaj/code-flow-skill/archive/refs/heads/master.zip and unzip
  ```

You only need the `templates/` directory. The rest of the repo (packaging, installer script, `src/`) can be ignored.

**2. Copy the template(s) for the tool(s) you use** into your target project.

From the project root where you want the skill available:

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

On Windows PowerShell, substitute `New-Item -ItemType Directory -Force` for `mkdir -p` and `Copy-Item` for `cp`.

If you skip the `.code-flow/viewer.template.html` step, the command still works — the assistant just falls back to a minimal Mermaid-based HTML page instead of the full interactive viewer.

**3. Verify.** Restart your assistant (or start a new session). In Claude Code or Gemini CLI, typing `/` should list the new `/code-flow.map` command. For Copilot in VS Code, look for the prompt in the Prompts picker (or try `/code-flow.map` in chat); on other Copilot surfaces, see the **GitHub Copilot** notes under *Usage*.

That's it — no install step runs any code on your machine. If you later want to update the skill, just re-copy the template files.

## CLI options

```text
code-flow-skill [--target PATH] [--tool claude|gemini|copilot|all]
```

Defaults: `--tool all`, `--target .`.

## Files written

| Tool | Path |
|------|------|
| Claude Code | `.claude/commands/code-flow.map.md` |
| Gemini CLI | `.gemini/commands/code-flow.map.toml` |
| GitHub Copilot | `.github/prompts/code-flow.map.prompt.md` |
| _All tools_ | `.code-flow/viewer.template.html` (interactive HTML scaffold) |

The `.code-flow/viewer.template.html` scaffold is tool-agnostic and is installed regardless of which `--tool` you select, since every command template references it.

## Packages

- npm: [`@htst/code-flow-skill`](https://www.npmjs.com/package/@htst/code-flow-skill)
- PyPI / uvx: `htst-code-flow-skill`

## Publishing

### npm

```bash
npm publish --access public
```

### PyPI

```bash
uv build
uv publish
```

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

Commercial use is welcome. If you use, redistribute, or fork this project, you **must**:

- Keep the `LICENSE` and `NOTICE` files intact.
- Preserve the copyright and attribution notices (credit to **Hightower Software Technologies**) in any derivative work.
- State any significant changes you made to the files.

See the `NOTICE` file for the required attribution text.
